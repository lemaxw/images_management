import asyncio
import json
import os
import re
import sys
import time
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path

from aws_translator import translate_word
from db_upsert_entity import get_poems, get_recent_first_place_ids, record_first_place
from tale_preparation import (
    call_ollama,
    caption_image,
    generate_location_from_tags,
    get_caption_backend,
    get_gps_coords,
    get_xmp_tags,
    reverse_geocode,
)
from sentences_comparator import SentenceMatcher
from telegram_send_msg import send_telegram_message


class TimingStats:
    """Collect and print elapsed time for the expensive publishing stages."""

    def __init__(self, enabled=None):
        if enabled is None:
            enabled = os.getenv("PUBLISH_TIMING", "1").lower() not in ("0", "false", "no")
        self.enabled = enabled
        self.slow_threshold = float(os.getenv("PUBLISH_TIMING_SLOW_THRESHOLD_SECONDS", "5"))
        self._stats = defaultdict(lambda: [0, 0.0])
        self.started_at = time.perf_counter()

    @contextmanager
    def measure(self, name):
        started_at = time.perf_counter()
        try:
            yield
        finally:
            if self.enabled:
                elapsed = time.perf_counter() - started_at
                stat = self._stats[name]
                stat[0] += 1
                stat[1] += elapsed
                if self.slow_threshold > 0 and elapsed >= self.slow_threshold:
                    print(f"[timing] {name}: {elapsed:.2f}s")

    def report(self):
        if not self.enabled:
            return
        elapsed = time.perf_counter() - self.started_at
        print("\nTiming summary:")
        for name, (count, total) in sorted(
            self._stats.items(), key=lambda item: item[1][1], reverse=True
        ):
            print(f"  {name:<32} {total:8.2f}s  calls={count:<3} avg={total / count:7.2f}s")
        print(f"  {'total wall time':<32} {elapsed:8.2f}s")


def _normalize_entity(entity):
    return " ".join(str(entity or "").split()).strip().lower()


def _rating_value(poem):
    try:
        return float(poem.get("rating") or 0)
    except (TypeError, ValueError):
        return 0.0


def _best_unique_entity_poems(poems):
    best_by_entity = {}
    for poem in poems:
        entity = poem.get("entity")
        if not entity:
            continue
        key = _normalize_entity(entity)
        existing = best_by_entity.get(key)
        if existing is None or _rating_value(poem) > _rating_value(existing):
            best_by_entity[key] = poem
    return list(best_by_entity.values())


def _poems_by_id(poems):
    return {str(poem.get("id")): poem for poem in poems if poem.get("id") is not None}


def select_top_poem_ids(
    location_str,
    caption,
    poems,
    timings=None,
    timing_prefix="selection",
    target_poems=None,
    entity_matcher=None,
    excluded_first_ids=None,
):
    """
    Select top poem IDs for one image. Generation is used only to bridge image
    context to poem entities; final publishing resolves exact poems by ID.
    """
    initial_loops = int(os.getenv("PUBLISH_INITIAL_LOOPS", "2"))
    improvement_loops = int(os.getenv("PUBLISH_IMPROVEMENT_LOOPS", "1"))
    batch_size = int(os.getenv("PUBLISH_INITIAL_BATCH_SIZE", "10"))
    improvement_batch_size = int(os.getenv("PUBLISH_IMPROVEMENT_BATCH_SIZE", "20"))
    top_size = int(os.getenv("PUBLISH_TOP_SIZE", "5"))
    seed_size = 10
    target_theme_size = 20

    target_poems = target_poems or _best_unique_entity_poems(poems)
    excluded_first_ids = {str(poem_id) for poem_id in (excluded_first_ids or set())}
    entities = [poem["entity"] for poem in target_poems]
    if not entities:
        return []

    if entity_matcher is None:
        with timings.measure(f"{timing_prefix}.semantic_index") if timings else _null_measure():
            entity_matcher = SentenceMatcher(entities)

    def best_entity(scores):
        best_idx, best_score = max(enumerate(scores), key=lambda item: item[1])
        return best_score, target_poems[best_idx]

    context = f"{caption} {location_str}".strip()
    with timings.measure(f"{timing_prefix}.semantic_context") if timings else _null_measure():
        context_scores = entity_matcher.score(context) if context else []
    image_scores_by_id = {
        str(target_poems[idx]["id"]): score
        for idx, score in enumerate(context_scores)
    }
    ranked_context = sorted(enumerate(context_scores), key=lambda item: item[1], reverse=True)
    target_themes = [(target_poems[idx], score) for idx, score in ranked_context[:target_theme_size]]

    def target_theme_text(limit=10):
        if not target_themes:
            return "No target themes available."
        return "\n".join(f"- {poem['entity']}" for poem, _ in target_themes[:limit])

    def build_initial_prompt():
        return (
            f"Image caption: {caption}\n"
            f"Location: {location_str}\n"
            "Target poem themes to aim toward:\n"
            f"{target_theme_text(12)}\n\n"
            f"Write {batch_size} metaphorical, one-line tales (< 300 chars each), "
            "inspired by the image. Each tale should connect the visible image to one target theme. "
            "Use concrete words from the target themes when they fit naturally. "
            "Return each tale on a separate line, with no explanation."
        )

    def build_improvement_prompt(top_tales):
        top_lines = "\n".join(
            f"- [{score:.2f} vs '{poem['entity']}'] {tale}"
            for tale, (score, poem) in top_tales
        )
        return (
            f"Image caption: {caption}\n"
            f"Location: {location_str}\n\n"
            "Target poem themes to aim toward:\n"
            f"{target_theme_text(15)}\n\n"
            "Current best tales:\n"
            f"{top_lines}\n\n"
            f"Write {improvement_batch_size} better one-line tales (< 300 chars each). "
            "Move each new tale closer to one target theme or to the matched theme shown beside a current best tale. "
            "Keep the image visible, use stronger shared vocabulary, and do not repeat existing tales exactly. "
            "Return each tale on a separate line, with no explanation."
        )

    def parse_tales(raw_tales):
        tales = []
        for line in raw_tales.split("\n"):
            tale = line.strip("-•0123456789. )\t").strip()
            if tale:
                tales.append(tale)
        return tales

    scored_by_tale = {}
    best_by_poem_id = {}
    seen = set()

    def add_tales(tales):
        new_tales = []
        for tale in tales:
            normalized = " ".join(tale.lower().split())
            if normalized in seen:
                continue
            seen.add(normalized)
            new_tales.append(tale)

        with timings.measure(f"{timing_prefix}.semantic_tales") if timings else _null_measure():
            score_rows = entity_matcher.score_many(new_tales)
        for tale, scores in zip(new_tales, score_rows):
            score, poem = best_entity(scores)
            poem_id = str(poem["id"])
            scored_by_tale[tale] = (score, poem)
            existing = best_by_poem_id.get(poem_id)
            if existing is None or score > existing[1]:
                best_by_poem_id[poem_id] = (poem, score, tale)

    def sorted_tales():
        return sorted(scored_by_tale.items(), key=lambda x: x[1][0], reverse=True)

    for _ in range(initial_loops):
        with timings.measure(f"{timing_prefix}.ollama_initial") if timings else _null_measure():
            raw_tales = call_ollama(build_initial_prompt(), temperature=0.7)
        add_tales(parse_tales(raw_tales))

    for _ in range(improvement_loops):
        previous_best = sorted_tales()[0][1][0] if scored_by_tale else 0.0
        top_tales = sorted_tales()[:seed_size]
        if not top_tales:
            break
        with timings.measure(f"{timing_prefix}.ollama_improve") if timings else _null_measure():
            raw_tales = call_ollama(build_improvement_prompt(top_tales), temperature=0.35)
        add_tales(parse_tales(raw_tales))
        current_best = sorted_tales()[0][1][0] if scored_by_tale else 0.0
        if current_best <= previous_best:
            break

    for poem, score in target_themes:
        if len(best_by_poem_id) >= top_size:
            break
        poem_id = str(poem["id"])
        if poem_id not in best_by_poem_id:
            best_by_poem_id[poem_id] = (poem, score, context)

    ranked_candidates = sorted(best_by_poem_id.values(), key=lambda x: x[1], reverse=True)
    first_eligible_idx = next(
        (
            idx
            for idx, (poem, _, _) in enumerate(ranked_candidates)
            if str(poem["id"]) not in excluded_first_ids
        ),
        None,
    )
    if first_eligible_idx is None:
        for target_idx, _ in ranked_context:
            poem = target_poems[target_idx]
            poem_id = str(poem["id"])
            if poem_id not in excluded_first_ids:
                ranked_candidates.append((poem, context_scores[target_idx], context))
                first_eligible_idx = len(ranked_candidates) - 1
                break
    if first_eligible_idx is None:
        print("No poem is eligible for first place during the two-week cooldown window")
        return []
    if first_eligible_idx:
        first_candidate = ranked_candidates.pop(first_eligible_idx)
        ranked_candidates.insert(0, first_candidate)
        print(
            f"First-place cooldown promoted poem id={first_candidate[0]['id']} "
            "ahead of recently first-ranked poems"
        )

    selected = ranked_candidates[:top_size]
    for idx, (poem, score, tale) in enumerate(selected, 1):
        image_score = image_scores_by_id.get(str(poem["id"]), score)
        print(
            f"{idx}. [generated tale score {score:.2f}, image score {image_score:.2f}] "
            f"{poem['entity']} | id={poem['id']}  <- {tale}"
        )

    return [
        {
            "id": str(poem["id"]),
            "generated_tale_score": score,
            "image_score": image_scores_by_id.get(str(poem["id"]), score),
        }
        for poem, score, _ in selected
    ]


@contextmanager
def _null_measure():
    yield


def _clean_poem_text(poem_text):
    text = str(poem_text or "")
    text = text.replace("<p>", "\n")
    text = text.replace("</p>", "\n")
    text = text.replace("<br>", "\n")
    text = text.replace("<br/>", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _clip_excerpt(text, max_lines=3):
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    return "\n".join(lines[:max_lines]).strip()


def _line_key(line):
    return re.sub(r"\s+", " ", str(line or "").strip()).lower()


def _excerpt_lines(text):
    return [line.strip() for line in str(text or "").splitlines() if line.strip() and line.strip() != "..."]


def _format_excerpt_with_context(poem_text, excerpt):
    poem_lines = _excerpt_lines(_clean_poem_text(poem_text))
    excerpt_lines = _excerpt_lines(excerpt)
    if not excerpt_lines:
        return ""

    poem_keys = [_line_key(line) for line in poem_lines]
    selected_indices = []
    search_from = 0
    for excerpt_line in excerpt_lines:
        excerpt_key = _line_key(excerpt_line)
        matched_idx = None
        for idx in range(search_from, len(poem_keys)):
            if poem_keys[idx] == excerpt_key:
                matched_idx = idx
                break
        if matched_idx is None:
            return ""
        selected_indices.append(matched_idx)
        search_from = matched_idx + 1

    formatted = []
    if selected_indices[0] > 0:
        formatted.append("...")
    previous_idx = None
    for idx, line in zip(selected_indices, excerpt_lines):
        if previous_idx is not None and idx > previous_idx + 1:
            formatted.append("...")
        formatted.append(line)
        previous_idx = idx
    if selected_indices[-1] + 1 < len(poem_lines):
        formatted.append("...")
    return "\n".join(formatted)


def select_poem_excerpt(poem, caption, tags, location):
    poem_text = _clean_poem_text(poem.get("text", ""))
    if not poem_text:
        return ""

    prompt = (
        f"Image caption: {caption}\n"
        f"Image tags: {tags}\n"
        f"Location: {location}\n"
        f"Poem entity/theme: {poem.get('entity', '')}\n\n"
        "From the poem below, select the exact excerpt that best represents the image. "
        "Use exactly 3 original poem lines if possible; otherwise use 2 lines, otherwise 1 line. "
        "Prefer more lines when they still fit the image. "
        "Copy lines only from the poem text, in the poem's original language. "
        "Do not return the poem entity/theme, translation, image description, rewritten text, explanations, ellipses, or added punctuation. "
        "Return only the excerpt.\n\n"
        f"Poem:\n{poem_text}"
    )
    excerpt = call_ollama(prompt, temperature=0.1)
    excerpt = re.sub(r"^```(?:\w+)?\s*|\s*```$", "", excerpt.strip(), flags=re.MULTILINE).strip()
    excerpt = _clip_excerpt(excerpt, max_lines=3)
    formatted_excerpt = _format_excerpt_with_context(poem_text, excerpt)
    if formatted_excerpt:
        return formatted_excerpt
    return _format_excerpt_with_context(poem_text, _clip_excerpt(poem_text, max_lines=3))


def select_poem_excerpts(poems, caption, tags, location):
    """Select validated excerpts for several poems with one Ollama request."""
    poems = [poem for poem in poems if _clean_poem_text(poem.get("text", ""))]
    if not poems:
        return {}

    poem_sections = []
    for poem in poems:
        poem_sections.append(
            f"<poem id=\"{poem['id']}\">\n"
            f"Theme: {poem.get('entity', '')}\n"
            f"{_clean_poem_text(poem.get('text', ''))}\n"
            "</poem>"
        )
    prompt = (
        f"Image caption: {caption}\n"
        f"Image tags: {tags}\n"
        f"Location: {location}\n\n"
        "For each poem below, select the exact excerpt that best represents the image. "
        "Use exactly 3 original poem lines if possible; otherwise use 2 lines, otherwise 1 line. "
        "Copy lines only from that poem, in its original language. "
        "Do not translate, rewrite, explain, or add punctuation. "
        "Return only one JSON object whose keys are poem IDs and whose values are arrays of selected lines.\n\n"
        + "\n\n".join(poem_sections)
    )
    raw_response = call_ollama(prompt, temperature=0.1)
    cleaned_response = re.sub(
        r"^```(?:json)?\s*|\s*```$", "", raw_response.strip(), flags=re.MULTILINE | re.IGNORECASE
    ).strip()
    cleaned_response = re.sub(
        r"<think>.*?</think>", "", cleaned_response, flags=re.IGNORECASE | re.DOTALL
    ).strip()
    object_start = cleaned_response.find("{")
    object_end = cleaned_response.rfind("}")
    if object_start >= 0 and object_end > object_start:
        cleaned_response = cleaned_response[object_start : object_end + 1]
    try:
        selected_lines = json.loads(cleaned_response)
    except (json.JSONDecodeError, TypeError):
        selected_lines = {}
    if not isinstance(selected_lines, dict):
        selected_lines = {}

    excerpts = {}
    fallback_ids = []
    for poem in poems:
        poem_id = str(poem["id"])
        lines = selected_lines.get(poem_id, [])
        if isinstance(lines, str):
            lines = _excerpt_lines(lines)
        if not isinstance(lines, list):
            lines = []
        candidate = "\n".join(str(line) for line in lines[:3])
        excerpt = _format_excerpt_with_context(poem["text"], candidate)
        if not excerpt:
            fallback_ids.append(poem_id)
            fallback = _clip_excerpt(_clean_poem_text(poem["text"]), max_lines=3)
            excerpt = _format_excerpt_with_context(poem["text"], fallback)
        excerpts[poem_id] = excerpt
    if fallback_ids:
        print(
            f"Excerpt batch returned {len(fallback_ids)} invalid or missing selection(s); "
            f"used original opening lines for IDs: {', '.join(fallback_ids)}"
        )
    return excerpts


def _iter_image_paths(directory):
    suffixes = {".jpg", ".jpeg"}
    return sorted(
        (
            path
            for path in Path(directory).iterdir()
            if path.is_file() and path.suffix.lower() in suffixes
        ),
        key=lambda path: path.name.lower(),
    )


def _language_configs(timings=None):
    configs = []
    language_details = [
        ("ua", "Ukrainian", lambda loc: translate_word(loc, "uk"), "Повний твір"),
        ("ru", "Russian", lambda loc: translate_word(loc, "ru"), "Полное произведение"),
        ("en", "English", lambda loc: loc, "Full poem"),
    ]
    for lang, label, location, word_link in language_details:
        with timings.measure(f"startup.database.{lang}") if timings else _null_measure():
            poems = get_poems(lang)
        configs.append(
            {
                "lang": lang,
                "label": label,
                "poems": poems,
                "location": location,
                "word_link": word_link,
            }
        )
    return configs


def publish_poem(
    image_path,
    poem,
    excerpt,
    location,
    word_link,
    generated_tale_score,
    image_score,
    just_print=False,
):
    print(
        f"Selected poem: {poem.get('author')} | {poem.get('entity')} | "
        f"rating={poem.get('rating')} | generated_tale_score={generated_tale_score:.2f} | "
        f"image_score={image_score:.2f} | id={poem.get('id')}"
    )
    print("Full poem:")
    print(_clean_poem_text(poem.get("text", "")))
    print("Excerpt:")
    print(excerpt)
    print()

    if just_print:
        return False

    return asyncio.run(
        send_telegram_message(
            poem["author"],
            excerpt,
            location,
            image_path,
            poem["link_to_source"],
            poem["id"],
            poem["entity"],
            poem["rating"],
            generated_tale_score,
            word_link,
        )
    )


def process_directory(directory=None, just_print=True):
    timings = TimingStats()
    images_dir = Path.home() / "images"
    directory = Path(directory) if directory is not None else images_dir
    with timings.measure("startup.caption_backend"):
        caption_backend = get_caption_backend()
    configs = _language_configs(timings)
    for cfg in configs:
        cfg["poems_by_id"] = _poems_by_id(cfg["poems"])
        cfg["target_poems"] = _best_unique_entity_poems(cfg["poems"])
        entities = [poem["entity"] for poem in cfg["target_poems"]]
        with timings.measure(f"startup.semantic_index.{cfg['lang']}"):
            cfg["entity_matcher"] = SentenceMatcher(entities) if entities else None
        with timings.measure(f"startup.first_place_cooldown.{cfg['lang']}"):
            cfg["recent_first_place_ids"] = get_recent_first_place_ids(
                cfg["lang"], cooldown_days=14
            )

    try:
        for filepath in _iter_image_paths(directory):
            filepath = str(filepath)
            with timings.measure("image.caption"):
                caption = caption_image(filepath, caption_backend)
            with timings.measure("image.metadata_tags"):
                tags_info = get_xmp_tags(filepath) or "No tags available"
            with timings.measure("image.gps"):
                coords = get_gps_coords(filepath)
            if coords:
                with timings.measure("image.reverse_geocode"):
                    location = reverse_geocode(coords) or "Unknown"
            else:
                with timings.measure("image.location_from_tags"):
                    location = generate_location_from_tags(tags_info, caption)

            print(f"\nImage: {Path(filepath).name}")
            print(f"Caption: {caption}")
            print(f"Tags: {tags_info}")
            print(f"Location: {location}")

            for cfg in configs:
                print(f"\n{cfg['label']} top poems:")
                with timings.measure(f"language.{cfg['lang']}.selection"):
                    selected_poems = select_top_poem_ids(
                        location,
                        caption,
                        cfg["poems"],
                        timings=timings,
                        timing_prefix=f"language.{cfg['lang']}.selection",
                        target_poems=cfg["target_poems"],
                        entity_matcher=cfg["entity_matcher"],
                        excluded_first_ids=cfg["recent_first_place_ids"],
                    )
                poems_to_publish = []
                for selected_poem in selected_poems:
                    poem_id = selected_poem["id"]
                    poem = cfg["poems_by_id"].get(str(poem_id))
                    if not poem:
                        print(f"no poem found for id: {poem_id}")
                        continue
                    poems_to_publish.append((selected_poem, poem))

                with timings.measure(f"language.{cfg['lang']}.excerpt"):
                    excerpts = select_poem_excerpts(
                        [poem for _, poem in poems_to_publish], caption, tags_info, location
                    )
                with timings.measure(f"language.{cfg['lang']}.translate_location"):
                    translated_location = cfg["location"](location)
                published = 0
                for rank, (selected_poem, poem) in enumerate(poems_to_publish):
                    excerpt = excerpts.get(str(poem["id"]), "")
                    with timings.measure(f"language.{cfg['lang']}.publish"):
                        published_successfully = publish_poem(
                            filepath,
                            poem,
                            excerpt,
                            translated_location,
                            cfg["word_link"],
                            selected_poem["generated_tale_score"],
                            selected_poem["image_score"],
                            just_print=just_print,
                        )
                    if rank == 0 and published_successfully:
                        with timings.measure(f"language.{cfg['lang']}.record_first_place"):
                            record_first_place(poem["id"], cfg["lang"])
                        cfg["recent_first_place_ids"].add(str(poem["id"]))
                    published += 1
                print(f"{cfg['label']} selected {published} poems")
    finally:
        timings.report()


if __name__ == "__main__":
    flag = True
    directory = None

    if len(sys.argv) > 1:
        val = sys.argv[1].lower()
        if val in ("false", "0", "no", "n"):
            flag = False
        elif val not in ("true", "1", "yes", "y"):
            directory = sys.argv[1]

    if len(sys.argv) > 2:
        directory = sys.argv[2]

    process_directory(directory, just_print=flag)
