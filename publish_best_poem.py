import asyncio
import re
import sys
from pathlib import Path

from aws_translator import translate_word
from db_upsert_entity import get_poems
from tale_preparation import (
    call_ollama,
    caption_image,
    generate_location_from_tags,
    get_caption_backend,
    get_gps_coords,
    get_xmp_tags,
    reverse_geocode,
)
from sentences_comparator import get_similar_sentences
from telegram_send_msg import send_telegram_message


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


def select_top_poem_ids(location_str, caption, poems):
    """
    Select top poem IDs for one image. Generation is used only to bridge image
    context to poem entities; final publishing resolves exact poems by ID.
    """
    initial_loops = 5
    improvement_loops = 2
    batch_size = 10
    improvement_batch_size = 20
    top_size = 5
    seed_size = 10
    target_theme_size = 20

    target_poems = _best_unique_entity_poems(poems)
    entities = [poem["entity"] for poem in target_poems]
    if not entities:
        return []

    def score_against_entities(text):
        scores = get_similar_sentences(text, entities)
        best_idx, best_score = max(enumerate(scores), key=lambda item: item[1])
        return best_score, target_poems[best_idx]

    context = f"{caption} {location_str}".strip()
    context_scores = get_similar_sentences(context, entities) if context else []
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
        for tale in tales:
            normalized = " ".join(tale.lower().split())
            if normalized in seen:
                continue
            seen.add(normalized)
            score, poem = score_against_entities(tale)
            poem_id = str(poem["id"])
            scored_by_tale[tale] = (score, poem)
            existing = best_by_poem_id.get(poem_id)
            if existing is None or score > existing[1]:
                best_by_poem_id[poem_id] = (poem, score, tale)

    def sorted_tales():
        return sorted(scored_by_tale.items(), key=lambda x: x[1][0], reverse=True)

    for _ in range(initial_loops):
        add_tales(parse_tales(call_ollama(build_initial_prompt(), temperature=0.7)))

    for _ in range(improvement_loops):
        previous_best = sorted_tales()[0][1][0] if scored_by_tale else 0.0
        top_tales = sorted_tales()[:seed_size]
        if not top_tales:
            break
        add_tales(parse_tales(call_ollama(build_improvement_prompt(top_tales), temperature=0.35)))
        current_best = sorted_tales()[0][1][0] if scored_by_tale else 0.0
        if current_best <= previous_best:
            break

    for poem, score in target_themes:
        if len(best_by_poem_id) >= top_size:
            break
        poem_id = str(poem["id"])
        if poem_id not in best_by_poem_id:
            best_by_poem_id[poem_id] = (poem, score, context)

    selected = sorted(best_by_poem_id.values(), key=lambda x: x[1], reverse=True)[:top_size]
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

    excerpt_keys = [_line_key(line) for line in excerpt_lines]
    start_idx = None
    for idx in range(0, len(poem_lines) - len(excerpt_lines) + 1):
        candidate_keys = [_line_key(line) for line in poem_lines[idx : idx + len(excerpt_lines)]]
        if candidate_keys == excerpt_keys:
            start_idx = idx
            break

    formatted = list(excerpt_lines)
    if start_idx is None:
        return "\n".join(formatted)

    if start_idx > 0:
        formatted.insert(0, "...")
    if start_idx + len(excerpt_lines) < len(poem_lines):
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
        "Prefer more lines when they still fit the image. Do not rewrite, translate, explain, add ellipses, or add punctuation. "
        "Return only the excerpt.\n\n"
        f"Poem:\n{poem_text}"
    )
    excerpt = call_ollama(prompt, temperature=0.1)
    excerpt = re.sub(r"^```(?:\w+)?\s*|\s*```$", "", excerpt.strip(), flags=re.MULTILINE).strip()
    excerpt = _clip_excerpt(excerpt, max_lines=3)
    excerpt = excerpt or _clip_excerpt(poem_text, max_lines=3)
    return _format_excerpt_with_context(poem_text, excerpt)


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


def _language_configs():
    return [
        {
            "lang": "ua",
            "label": "Ukrainian",
            "poems": get_poems("ua"),
            "location": lambda loc: translate_word(loc, "uk"),
            "word_link": "Повний твір",
        },
        {
            "lang": "ru",
            "label": "Russian",
            "poems": get_poems("ru"),
            "location": lambda loc: translate_word(loc, "ru"),
            "word_link": "Полное произведение",
        },
        {
            "lang": "en",
            "label": "English",
            "poems": get_poems("en"),
            "location": lambda loc: loc,
            "word_link": "Full poem",
        },
    ]


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
        return

    asyncio.run(
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
    images_dir = Path.home() / "images"
    directory = Path(directory) if directory is not None else images_dir
    caption_backend = get_caption_backend()
    configs = _language_configs()
    for cfg in configs:
        cfg["poems_by_id"] = _poems_by_id(cfg["poems"])

    for filepath in _iter_image_paths(directory):
        filepath = str(filepath)
        caption = caption_image(filepath, caption_backend)
        tags_info = get_xmp_tags(filepath) or "No tags available"
        coords = get_gps_coords(filepath)
        if coords:
            location = reverse_geocode(coords) or "Unknown"
        else:
            location = generate_location_from_tags(tags_info, caption)

        print(f"\nImage: {Path(filepath).name}")
        print(f"Caption: {caption}")
        print(f"Tags: {tags_info}")
        print(f"Location: {location}")

        for cfg in configs:
            print(f"\n{cfg['label']} top poems:")
            selected_poems = select_top_poem_ids(location, caption, cfg["poems"])
            published = 0
            for selected_poem in selected_poems:
                poem_id = selected_poem["id"]
                poem = cfg["poems_by_id"].get(str(poem_id))
                if not poem:
                    print(f"no poem found for id: {poem_id}")
                    continue
                excerpt = select_poem_excerpt(poem, caption, tags_info, location)
                publish_poem(
                    filepath,
                    poem,
                    excerpt,
                    cfg["location"](location),
                    cfg["word_link"],
                    selected_poem["generated_tale_score"],
                    selected_poem["image_score"],
                    just_print=just_print,
                )
                published += 1
            print(f"{cfg['label']} selected {published} poems")


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
