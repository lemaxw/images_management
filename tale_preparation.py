import logging, sys, os, re
from pathlib import Path
import requests
import torch
from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from geopy.geocoders import Nominatim
from dotenv import load_dotenv
import subprocess, json
import piexif
from db_upsert_entity import get_poems
from sentences_comparator import get_similar_sentences

# load the environment variables from the .env file
load_dotenv()

# Caption backend interface
class CaptionBackend:
    """Abstract base class for image captioning backends."""
    def caption_image(self, filepath: str) -> str:
        """Generate caption for image at filepath."""
        raise NotImplementedError


class BlipCaptionBackend(CaptionBackend):
    """BLIP-based image captioning backend."""
    def __init__(self):
        self.processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-large")
        self.model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-large")
        self.model.eval()
    
    def caption_image(self, filepath: str) -> str:
        """Open the JPEG and return a detailed, multi-sentence caption."""
        with Image.open(filepath) as img:
            img = img.convert("RGB")
        prompt_text = "Describe this photograph in 2-3 vivid sentences."
        inputs = self.processor(images=img, text=prompt_text, return_tensors="pt")
        with torch.no_grad():
            output_ids = self.model.generate(
                **inputs,
                min_new_tokens=40,
                max_new_tokens=80,
                num_beams=5,
                length_penalty=1.0,
                early_stopping=True,
                no_repeat_ngram_size=3
            )
        caption = self.processor.decode(output_ids[0], skip_special_tokens=True).strip()
        caption = re.sub(
            r"^\s*describe this photograph in\s*\d+\s*[-–]?\s*\d*\s*vivid sentences[.\s,-]*",
            "",
            caption,
            flags=re.IGNORECASE
        ).strip(" ,.-")
        logging.info(f"Generated caption: {caption} for file {filepath}")
        return caption


class Image2JsonCaptionBackend(CaptionBackend):
    """image2json-based image captioning backend."""
    def __init__(self):
        try:
            from image2json.analyzer import ImageAnalyzer
            from image2json.config import AnalysisConfig
            config = AnalysisConfig(short_version=True)
            self.analyzer = ImageAnalyzer(config=config)
        except ImportError as e:
            logging.error(f"Failed to import image2json: {e}")
            raise
    
    def caption_image(self, filepath: str) -> str:
        """Generate caption using image2json."""
        try:
            analysis = self.analyzer.analyze_path(Path(filepath))
            # Use detailed_description if it exists and is not empty, otherwise fall back to summary
            caption = analysis.detailed_description if analysis.detailed_description else analysis.summary
            logging.info(f"Generated caption: {caption} for file {filepath}")
            return caption
        except Exception as e:
            logging.error(f"Failed to generate caption with image2json: {e}")
            raise


# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "WARNING").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.WARNING),
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)  # Log to console
    ]
)

OLLAMA_URL = os.getenv("OLLAMA_URL") or os.getenv("IMAGE2JSON_URL") or "http://localhost:11434"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL") or os.getenv("IMAGE2JSON_TEXT_MODEL") or "muse-glimmer-text:latest"
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT") or os.getenv("IMAGE2JSON_TIMEOUT") or "300")
OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "10m")


def call_ollama(
    prompt: str,
    *,
    model: str | None = None,
    timeout: int | None = None,
    temperature: float = 0.2,
) -> str:
    """Call the local Ollama text model and return plain response text."""
    payload = {
        "model": model or OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "keep_alive": OLLAMA_KEEP_ALIVE,
        "options": {"temperature": temperature},
    }
    url = f"{OLLAMA_URL.rstrip('/')}/api/generate"
    response = requests.post(url, json=payload, timeout=timeout or OLLAMA_TIMEOUT)
    response.raise_for_status()
    text = response.json().get("response", "")
    text = re.sub(r"^```(?:\w+)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)
    return text.strip()


def get_caption_backend(backend_name: str = None) -> CaptionBackend:
    """Get caption backend by name. Defaults to BLIP."""
    if backend_name is None:
        backend_name = os.getenv("CAPTION_BACKEND", "image2json").lower()
    
    if backend_name == "blip":
        return BlipCaptionBackend()
    elif backend_name == "image2json":
        return Image2JsonCaptionBackend()
    else:
        logging.warning(f"Unknown backend '{backend_name}', defaulting to BLIP")
        return BlipCaptionBackend()


def caption_image(filepath, backend: CaptionBackend = None):
    """Open the JPEG and return a detailed, multi-sentence caption.
    
    Args:
        filepath: Path to the image file
        backend: Optional CaptionBackend instance. If None, uses backend from CAPTION_BACKEND env var or defaults to BLIP.
    """
    if backend is None:
        backend = get_caption_backend()
    return backend.caption_image(filepath)

def get_xmp_tags(filepath):
    """
    Uses exiftool to read XMP/IPTC keywords and subject.
    Returns a string like "Landscape; israel; timna" or None.
    """
    try:
        # -j: JSON output, -Keywords and -Subject tags
        out = subprocess.check_output(
            ["exiftool", "-j", "-Keywords", "-Subject", filepath],
            stderr=subprocess.DEVNULL
        )
        data = json.loads(out)[0]
        tags = []
        for key in ("Keywords", "Subject"):
            v = data.get(key)
            if isinstance(v, list):
                tags.extend(v)
            elif v:
                tags.append(v)
        logging.info(f"Generated tags: {tags} for file {filepath}")
        return "; ".join(tags) if tags else None
    except Exception:
        return None


def get_gps_coords(filepath):
    """
    filepath: path to the JPEG on disk.
    Returns (lat, lon) in decimal degrees, or None if no GPS EXIF.
    """
    try:
        exif_dict = piexif.load(filepath)
    except Exception as e:
        logging.warning("Failed to load EXIF for %s: %s", filepath, e)
        return None

    gps_ifd = exif_dict.get("GPS", {})
    if not gps_ifd:
        logging.debug("No GPS IFD found in EXIF for %s", filepath)
        return None

    # pull out latitude/longitude tuples + refs
    lat_tuple = gps_ifd.get(piexif.GPSIFD.GPSLatitude)
    lat_ref   = gps_ifd.get(piexif.GPSIFD.GPSLatitudeRef)
    lon_tuple = gps_ifd.get(piexif.GPSIFD.GPSLongitude)
    lon_ref   = gps_ifd.get(piexif.GPSIFD.GPSLongitudeRef)
    if not (lat_tuple and lat_ref and lon_tuple and lon_ref):
        logging.debug(
            "Incomplete GPS tags for %s: lat_tuple=%r lat_ref=%r lon_tuple=%r lon_ref=%r",
            filepath, lat_tuple, lat_ref, lon_tuple, lon_ref
        )
        return None

    def _to_deg(rational_triplet):
        d = rational_triplet[0][0] / rational_triplet[0][1]
        m = rational_triplet[1][0] / rational_triplet[1][1]
        s = rational_triplet[2][0] / rational_triplet[2][1]
        return d + m/60 + s/3600

    lat = _to_deg(lat_tuple)
    if lat_ref in (b'S', 'S'):  # southern hemisphere
        lat = -lat

    lon = _to_deg(lon_tuple)
    if lon_ref in (b'W', 'W'):  # western hemisphere
        lon = -lon

    logging.debug("Extracted GPS coordinates for %s: (%f, %f)", filepath, lat, lon)
    return (lat, lon)


def reverse_geocode(coords):
    """Translate coordinates to 'City, Country' using Nominatim."""
    geolocator = Nominatim(user_agent="tale_generator")
    try:
        location = geolocator.reverse(f"{coords[0]}, {coords[1]}", language="en", addressdetails=True)
        if location and 'address' in location.raw:
            addr = location.raw['address']
            city = (
                addr.get('city')
                or addr.get('town')
                or addr.get('village')
                or addr.get('hamlet')
                or addr.get('municipality')
                or addr.get('county')
                or addr.get('state')
            )
            country = addr.get('country')
            if city and country:
                return f"{city}, {country}"
    except Exception:
        pass
    return None


def _normalize_location_text(text):
    return " ".join(str(text or "").strip(" .,:;-'\"").split())


def _parse_location_response(raw_location):
    """Extract a 'Place, Country' answer from an Ollama response."""
    raw_location = str(raw_location or "").strip()
    if not raw_location:
        return "Unknown"

    text = re.sub(r"<think>.*?</think>", "", raw_location, flags=re.IGNORECASE | re.DOTALL).strip()
    if not text:
        return "Unknown"

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        place = _normalize_location_text(
            parsed.get("place") or parsed.get("city") or parsed.get("region")
        )
        country = _normalize_location_text(parsed.get("country"))
        if place and country:
            return f"{place}, {country}"

    place_match = re.search(
        r"\b(?:place|city|region)\s*[:=-]\s*([A-Za-z][A-Za-z .'-]+)",
        text,
        re.IGNORECASE,
    )
    country_match = re.search(r"\bcountry\s*[:=-]\s*([A-Za-z][A-Za-z .'-]+)", text, re.IGNORECASE)
    if place_match and country_match:
        place = _normalize_location_text(place_match.group(1).splitlines()[0])
        country = _normalize_location_text(country_match.group(1).splitlines()[0])
        if place and country:
            return f"{place}, {country}"

    if text.lower().startswith("unknown"):
        return "Unknown"

    candidates = []
    for match in re.finditer(r"([A-Za-z][A-Za-z .'-]*?),\s*([A-Za-z][A-Za-z .'-]+)", text):
        city = _normalize_location_text(match.group(1))
        country = _normalize_location_text(match.group(2).splitlines()[0])
        city = re.sub(r"^(?:the\s+)?(?:most\s+likely\s+)?(?:location|answer)\s+(?:is|:)\s+", "", city, flags=re.IGNORECASE)
        if city and country:
            candidates.append(f"{city}, {country}")
    if candidates:
        return min(candidates, key=len)

    return "Unknown"


def generate_location_from_tags(tags_info, caption=None):
    """Ask the local Ollama text model to infer a place from tags/description."""
    caption_clause = f"Image caption, visual context only: {caption}\n" if caption else ""
    prompt = (
        "Infer the most likely photo location.\n"
        "Priority rules:\n"
        "1. Photo metadata tags are the primary evidence.\n"
        "2. The image caption is only visual context and must not override explicit place or country tags.\n"
        "3. Tags may contain misspellings, transliterations, duplicates, hyphenated names, or mixed capitalization.\n\n"
        f"Photo metadata tags: {tags_info}\n"
        f"{caption_clause}\n"
        "Find explicit place-like tags and country tags. A place may be a city, town, village, "
        "region, national park, mountain area, landmark, or other named geographic area. "
        "Convert place names to standard English spelling.\n"
        "Return exactly one line as Place, Country. "
        "If the tags do not contain a plausible named place and country, return exactly Unknown."
    )
    raw_location = call_ollama(prompt, temperature=0.0)
    location = _parse_location_response(raw_location)
    logging.info(f"Generated location: {location} (raw response: {raw_location})")
        
    return location

def generate_tale(location_str, caption, entities):
    """
    Generate one-line metaphorical tales based on image caption and location,
    then return the top unique matched poem entities.
    First generate 5 independent batches of 10 tales. Then use the best 10
    candidates for up to 2 improvement rounds, stopping if a round does not
    improve the best score. Print the final top 5 entities.
    """
    initial_loops = 5
    improvement_loops = 2
    batch_size = 10
    improvement_batch_size = 20
    top_size = 5
    seed_size = 10
    target_theme_size = 20

    def score_against_entities(text):
        if not entities:
            return 0.0, ""
        scores = get_similar_sentences(text, entities)
        best_idx, best_score = max(enumerate(scores), key=lambda item: item[1])
        return best_score, entities[best_idx]

    context = f"{caption} {location_str}".strip()
    target_themes = []
    if entities and context:
        context_scores = get_similar_sentences(context, entities)
        ranked_context = sorted(enumerate(context_scores), key=lambda item: item[1], reverse=True)
        target_themes = [(entities[idx], score) for idx, score in ranked_context[:target_theme_size]]
        logging.info("Top target themes from image context:")
        for idx, (theme, score) in enumerate(target_themes[:10], 1):
            logging.info(f"{idx}. [{score:.2f}] {theme}")

    def target_theme_text(limit=10):
        if not target_themes:
            return "No target themes available."
        return "\n".join(f"- {theme}" for theme, _ in target_themes[:limit])

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
            f"- [{score:.2f} vs '{matched_entity}'] {tale}"
            for tale, (score, matched_entity) in top_tales
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
    best_by_entity = {}
    seen = set()

    def add_tales(tales, stage, loop_idx):
        for tale in tales:
            normalized = " ".join(tale.lower().split())
            if normalized in seen:
                continue
            seen.add(normalized)
            score, matched_entity = score_against_entities(tale)
            scored_by_tale[tale] = (score, matched_entity)
            if matched_entity:
                entity_key = " ".join(matched_entity.lower().split())
                existing = best_by_entity.get(entity_key)
                if existing is None or score > existing[1]:
                    best_by_entity[entity_key] = (matched_entity, score, tale)
            logging.info(f"{stage} {loop_idx}: Tale: {tale} (Score: {score:.2f}, Entity: {matched_entity})")

    def sorted_tales():
        return sorted(scored_by_tale.items(), key=lambda x: x[1][0], reverse=True)

    for loop_idx in range(1, initial_loops + 1):
        add_tales(parse_tales(call_ollama(build_initial_prompt(), temperature=0.7)), "Initial", loop_idx)
        best_score = sorted_tales()[0][1][0] if scored_by_tale else 0.0
        logging.info(f"Initial {loop_idx}: best tale score so far: {best_score:.2f}")

    for loop_idx in range(1, improvement_loops + 1):
        previous_best = sorted_tales()[0][1][0] if scored_by_tale else 0.0
        top_tales = sorted_tales()[:seed_size]
        if not top_tales:
            break
        add_tales(parse_tales(call_ollama(build_improvement_prompt(top_tales), temperature=0.35)), "Improve", loop_idx)
        current_best = sorted_tales()[0][1][0] if scored_by_tale else 0.0
        logging.info(f"Improve {loop_idx}: best tale score changed from {previous_best:.2f} to {current_best:.2f}")
        if current_best <= previous_best:
            logging.info("Stopping improvement because best score did not improve.")
            break

    for theme, score in target_themes:
        if len(best_by_entity) >= top_size:
            break
        entity_key = " ".join(theme.lower().split())
        if entity_key not in best_by_entity:
            best_by_entity[entity_key] = (theme, score, context)

    scored_entities = sorted(best_by_entity.values(), key=lambda x: x[1], reverse=True)

    for idx, (entity, score, tale) in enumerate(scored_entities[:top_size], 1):
        print(f"{idx}. [{score:.2f}] {entity}  <- {tale}")

    return [entity for entity, _, _ in scored_entities[:top_size]]


def select_tale(captions):
    """Now feed *both* the caption and location into ChatGPT."""
    best_score = float("-inf")
    best_result = None

    poems_en =  get_poems('en')
    entities = [poem['entity'] for poem in poems_en if 'entity' in poem]

    for attempt in range(0,4):
        current_tale = captions[attempt]
        current_score = max(get_similar_sentences(current_tale, entities))
        logging.info(f"Generated tale: {current_tale} (best similarity score: {current_score:.2f})")

        if current_score > best_score:
            best_score = current_score
            best_tale = current_tale
        

    return best_tale

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

def process_directory(directory=None, output_path=None):
    """Process all JPEG files in a directory."""
    images_dir = Path.home() / "images"
    directory = Path(directory) if directory is not None else images_dir
    output_dir = Path(output_path).parent if output_path is not None else images_dir
    languages = {
        "ua": {
            "label": "Ukrainian",
            "output": output_dir / "input_ua",
            "poems": get_poems("ua"),
        },
        "ru": {
            "label": "Russian",
            "output": output_dir / "input_ru",
            "poems": get_poems("ru"),
        },
        "en": {
            "label": "English",
            "output": output_dir / "input_en",
            "poems": get_poems("en"),
        },
    }
    for cfg in languages.values():
        cfg["entities"] = [poem["entity"] for poem in cfg["poems"] if poem.get("entity")]

    with (
        open(languages["en"]["output"], "w", encoding="utf-8") as out_en,
        open(languages["ru"]["output"], "w", encoding="utf-8") as out_ru,
        open(languages["ua"]["output"], "w", encoding="utf-8") as out_ua,
    ):
        outputs = {"en": out_en, "ru": out_ru, "ua": out_ua}
        for filepath in _iter_image_paths(directory):
            filepath = str(filepath)
            caption = caption_image(filepath)
            tags_info = get_xmp_tags(filepath) or "No tags available"
            coords = get_gps_coords(filepath)
            if coords:
                location = reverse_geocode(coords) or "Unknown"
            else:
                logging.info(f"Processing file {filepath} found following tags: {tags_info}")
                location = generate_location_from_tags(tags_info, caption)
            print(f"\nImage: {Path(filepath).name}")
            print(f"Caption: {caption}")
            print(f"Tags: {tags_info}")
            for lang, cfg in languages.items():
                print(f"{cfg['label']} top entities:")
                entities = generate_tale(location, caption, cfg["entities"])
                for entity in entities:
                    print(f"{location}|{filepath}|{entity}", file=outputs[lang])



if __name__ == "__main__":    
   process_directory()
   #select_tale(["Smoke curls between gold and stone, carrying whispers of ancient trade.","A thousand colors rest in shadow, waiting for the sun to stir them awake.",
#"The alley hums with quiet footsteps and the scent of brass and spice.", "Trinkets gleam like small suns in the cool heart of the market.", 
#"Every arch and lantern tells a story that time forgot to close."])
