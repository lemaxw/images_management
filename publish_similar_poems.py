import asyncio, os

from PIL import Image
from db_upsert_entity import get_poems
from telegram_send_msg import send_telegram_message
from clip_find_similarity import find_similarities

def publish_similarities(image, entities, poems):
    similarities = find_similarities(image, entities)
    print("found similarities")

    # Pair each text with its corresponding similarity
    poem_similarity_pairs = list(zip(poems, similarities))

    # Sort the pairs by similarity in descending order
    poem_similarity_pairs.sort(key=lambda x: x[1], reverse=True)
    
    count = 0
    # Print each pair on a new line
    for poem, similarity in poem_similarity_pairs:
        if similarity <= 0.02:
            print(f"found {count} similar poems")
            break;
        else:
            count = count + 1
            print(f"{similarity:.2f}: {poem['entity']}")
            asyncio.run(send_telegram_message(poem['author'],poem['text'],'replace',image_path,poem['link_to_source'],poem['id'],poem['entity'],poem['rating'], similarity))


# List of potential texts
poems_ua =  get_poems('ua')
entities_ua = [poem['entity'] for poem in poems_ua if 'entity' in poem]
poems_ru =  get_poems('ru')
entities_ru = [poem['entity'] for poem in poems_ru if 'entity' in poem]
print(f"got {len(entities_ua)} entities for ua, {len(entities_ru)} entities for ru")

# Preprocess the image
dir_path = "/home/mpshater/images"
for path in os.listdir(dir_path):
    if path.endswith(".jpg"):
        image_path=os.path.join(dir_path, path)
        print(f"start processing: {image_path}")
        image = Image.open(image_path)

        publish_similarities(image, entities_ua, poems_ua)
        publish_similarities(image, entities_ru, poems_ru)
 

