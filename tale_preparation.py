import logging, sys, os, glob
import openai
from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from geopy.geocoders import Nominatim
from dotenv import load_dotenv
import subprocess, json
import piexif
from image_manipulation import resize_image

# load the environment variables from the .env file
load_dotenv()
# 1) load your vision‐to‐text model once
processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
caption_model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")


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
    """Open the JPEG and return a one‐sentence caption."""
    
    img = resize_image(filepath, 512).convert("RGB")
    inputs = processor(img, return_tensors="pt")
    # out = caption_model.generate(**inputs, max_length=150, min_length=50)    
    # roughly speaking: 1 token ≈ 4 chars, so for 50–150 chars use ~12–40 tokens
    output_ids = caption_model.generate(
        **inputs,
        min_new_tokens=20,        # at least ~12 tokens (~48 chars)
        max_new_tokens=40,        # at most ~40 tokens (~160 chars)
        num_beams=5,              # beam search with 5 beams for quality
        length_penalty=1.5,       # no bias towards long/short
        early_stopping=True,      # stop once beams finish
        no_repeat_ngram_size=2,   # avoid immediate n-gram repeats
    )
    caption = processor.decode(output_ids[0], skip_special_tokens=True)
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
            city = addr.get('city') or addr.get('town') or addr.get('village') or addr.get('state')
            country = addr.get('country')
            if city and country:
                return f"{city}, {country}"
    except Exception:
        pass
    return None

def generate_location_from_tags(tags_info):
    """Ask OpenAI to infer location from tags/description."""
    prompt = (
        f"Based on these photo tags and description: {tags_info}, "
        "identify the most likely city and country where the photo was taken in the format 'City, Country'. "
        "If unknown, reply 'Unknown'."
    )    
    resp = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role":"user","content":prompt}]
    )
    location = resp.choices[0].message.content.strip()
    logging.info(f"Generated location: {location}")
        
    return location

def generate_tale(location_str, caption):
    """Now feed *both* the caption and location into ChatGPT."""
    prompt = (
        f"Image caption: {caption}\n"
        f"Location: {location_str}\n\n"
        "Write a super-short tale in one line (≤150 chars) "
        "inspired by the image content above."
    )
    resp = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role":"user","content":prompt}]
    )
    tale = resp.choices[0].message.content.strip()
    logging.info(f"Generated tale: {tale}")
    return tale

def process_directory(directory="/home/mpshater/images", output_path="/home/mpshater/images/input.txt"):
    """Process all JPEG files in a directory."""
    with open(output_path, "w", encoding="utf-8") as out:
        patterns = ("*.jpg", "*.jpeg", "*.JPG", "*.JPEG")
        for pattern in patterns:
            for filepath in glob.glob(os.path.join(directory, pattern)):
                coords = get_gps_coords(filepath)
                if coords:
                    location = reverse_geocode(coords) or "Unknown"
                else:
                    tags_info = get_xmp_tags(filepath) or "No tags available"
                    logging.info(f"Processing file {filepath} found following tags: {tags_info}")
                    location = generate_location_from_tags(tags_info)
                caption = caption_image(filepath)
                tale = generate_tale(location, caption)
                print(f"{location}|{filepath}|{tale}", file=out)



if __name__ == "__main__":    
   process_directory()
