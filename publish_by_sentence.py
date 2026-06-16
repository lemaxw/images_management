import asyncio
import sys
from pathlib import Path
from db_upsert_entity import get_poems
from telegram_send_msg import send_telegram_message
from aws_translator import translate_word


def _normalize_entity(entity):
    return " ".join(str(entity or "").split()).strip().lower()


def _rating_value(poem):
    try:
        return float(poem.get("rating") or 0)
    except (TypeError, ValueError):
        return 0.0


def find_poem_by_entity(entity, poems):
    normalized = _normalize_entity(entity)
    matches = [poem for poem in poems if _normalize_entity(poem.get("entity")) == normalized]
    if not matches:
        return None
    return sorted(matches, key=_rating_value, reverse=True)[0]


def publish_entity(image, entity, poems, location, word_link, just_print=False):
    poem = find_poem_by_entity(entity, poems)
    if not poem:
        print(f"no exact poem found for entity: {entity}")
        return

    print(f"{_rating_value(poem):.2f}: {poem['entity']}")
    if not just_print:
        asyncio.run(
            send_telegram_message(
                poem["author"],
                poem["text"],
                location,
                image,
                poem["link_to_source"],
                poem["id"],
                poem["entity"],
                poem["rating"],
                1.0,
                word_link,
            )
        )

def process_file(just_print=False):
    """
    Process language-specific input files and publish the exact entity match
    for each line.
    """   
    configs = [
        {
            "lang": "ua",
            "input": Path.home() / "images" / "input_ua",
            "poems": get_poems("ua"),
            "location": lambda loc: translate_word(loc, "uk"),
            "word_link": "Повний твір",
        },
        {
            "lang": "ru",
            "input": Path.home() / "images" / "input_ru",
            "poems": get_poems("ru"),
            "location": lambda loc: translate_word(loc, "ru"),
            "word_link": "Полное произведение",
        },
        {
            "lang": "en",
            "input": Path.home() / "images" / "input_en",
            "poems": get_poems("en"),
            "location": lambda loc: loc,
            "word_link": "Full poem",
        },
    ]

    delimiter = "|"

    for cfg in configs:
        input_file = cfg["input"]
        if not input_file.exists():
            print(f"missing input file for {cfg['lang']}: {input_file}")
            continue

        print(f"processing {cfg['lang']} from {input_file}")
        with open(input_file, "r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split(delimiter, 2)
                if len(parts) != 3:
                    print(f"skipping malformed line in {input_file}: {line}")
                    continue

                location, filename, entity = parts
                print(f"Filename: {filename}, entity: {entity}")
                publish_entity(
                    filename,
                    entity,
                    cfg["poems"],
                    cfg["location"](location),
                    cfg["word_link"],
                    just_print,
                )



if __name__ == "__main__":    
   # Default = True
    flag = True  

    # If a parameter is passed, interpret it
    if len(sys.argv) > 1:
        val = sys.argv[1].lower()
        if val in ("false", "0", "no", "n", "False"):
            flag = False
        else:
            flag = True
    
    process_file(flag)
