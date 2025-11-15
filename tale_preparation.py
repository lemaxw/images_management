import logging, sys, os, glob, re
import openai
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
# 1) load your vision‐to‐text model once
processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-large")
caption_model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-large")
caption_model.eval()


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)  # Log to console
    ]
)

# Ensure your OpenAI API key is set:
openai.api_key = os.getenv("OPENAI_API_KEY")


def caption_image(filepath):
    """Open the JPEG and return a detailed, multi-sentence caption."""

    with Image.open(filepath) as img:
        img = img.convert("RGB")
    prompt_text = "Describe this photograph in 2-3 vivid sentences."
    inputs = processor(images=img, text=prompt_text, return_tensors="pt")
    with torch.no_grad():
        output_ids = caption_model.generate(
            **inputs,
            min_new_tokens=40,
            max_new_tokens=80,
            num_beams=5,
            length_penalty=1.0,
            early_stopping=True,
            no_repeat_ngram_size=3
        )
    caption = processor.decode(output_ids[0], skip_special_tokens=True).strip()
    caption = re.sub(
        r"^\s*describe this photograph in\s*\d+\s*[-–]?\s*\d*\s*vivid sentences[.\s,-]*",
        "",
        caption,
        flags=re.IGNORECASE
    ).strip(" ,.-")
    logging.info(f"Generated caption: {caption} for file {filepath}")
    return caption

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

def generate_location_from_tags(tags_info, caption=None):
    """Ask OpenAI to infer location from tags/description."""
    caption_clause = f"\nImage caption hint: {caption}" if caption else ""
    prompt = (
        f"Based on these photo tags and description: {tags_info}, "
        "identify the most likely city and country where the photo was taken in the format 'City, Country'. "
        "If unknown, reply 'Unknown'."
        f"{caption_clause}\nReturn only the city and country."
    )    
    resp = openai.ChatCompletion.create(
       # model="gpt-3.5-turbo",
        model="gpt-4o-mini",
        messages=[{"role":"user","content":prompt}]
    )
    raw_location = resp.choices[0].message.content.strip()
    first_line = raw_location.splitlines()[0].strip()
    match = re.search(r"[A-Za-z][A-Za-z .'-]+,\s*[A-Za-z][A-Za-z .'-]+", first_line)
    if match:
        location = " ".join(match.group(0).split())
    elif first_line.lower().startswith("unknown"):
        location = "Unknown"
    else:
        location = "Unknown"
    logging.info(f"Generated location: {location} (raw response: {raw_location})")
        
    return location

def generate_tale(location_str, caption, entities):
    """
    Generate 5 one-line metaphorical tales based on image caption and location.
    Score each tale by similarity to entities, sort them by score descending,
    and return the best one.
    """
    prompt = (
        f"Image caption: {caption}\n"
        f"Location: {location_str}\n\n"
        "Write 5 metaphorical, super-short one-line tales (≤150 chars each), "
        "inspired by the image above. Return each tale on a separate line."
    )

    resp = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    # Split response into individual tales
    tales = [line.strip("-•0123456789. ").strip() for line in resp.choices[0].message.content.strip().split("\n") if line.strip()]
    
    scored_tales = []
    for tale in tales:
        score = max(get_similar_sentences(tale, entities))
        scored_tales.append((tale, score))
        logging.info(f"Tale: {tale} (Score: {score:.2f})")

    # Sort tales by score descending
    scored_tales.sort(key=lambda x: x[1], reverse=True)

    # Optionally: print top tales
    for idx, (tale, score) in enumerate(scored_tales, 1):
        print(f"{idx}. [{score:.2f}] {tale}")

    best_tale = scored_tales[0][0] if scored_tales else ""
    return best_tale


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

def process_directory(directory="/home/mpshater/images", output_path="/home/mpshater/images/input.txt"):
    """Process all JPEG files in a directory."""
    poems_en =  get_poems('en')
    entities_en = [poem['entity'] for poem in poems_en if 'entity' in poem]

    with open(output_path, "w", encoding="utf-8") as out:
        patterns = ("*.jpg", "*.jpeg", "*.JPG", "*.JPEG")
        for pattern in patterns:
            for filepath in glob.glob(os.path.join(directory, pattern)):
                caption = caption_image(filepath)
                coords = get_gps_coords(filepath)
                if coords:
                    location = reverse_geocode(coords) or "Unknown"
                else:
                    tags_info = get_xmp_tags(filepath) or "No tags available"
                    logging.info(f"Processing file {filepath} found following tags: {tags_info}")
                    location = generate_location_from_tags(tags_info, caption)
                tale = generate_tale(location, caption, entities_en)
                print(f"{location}|{filepath}|{tale}", file=out)



if __name__ == "__main__":    
   process_directory()
   #select_tale(["Smoke curls between gold and stone, carrying whispers of ancient trade.","A thousand colors rest in shadow, waiting for the sun to stir them awake.",
#"The alley hums with quiet footsteps and the scent of brass and spice.", "Trinkets gleam like small suns in the cool heart of the market.", 
#"Every arch and lantern tells a story that time forgot to close."])
