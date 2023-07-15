import asyncio, os

from PIL import Image
from db_upsert_entity import get_poems
from telegram_send_msg import send_telegram_message
from clip_find_similarity import find_similarities

# List of potential texts
poems =  get_poems()
entities = [poem['entity'] for poem in poems if 'entity' in poem]
print(f"got {len(entities)} entities")

# Preprocess the image
dir_path = "/home/mpshater/images"
for path in os.listdir(dir_path):
    if path.endswith(".jpg"):
        image_path=os.path.join(dir_path, path)
        print(f"start processing: {image_path}")
        image = Image.open(image_path)

        similarities = find_similarities(image, entities)
        print("found similarities")


        # Pair each text with its corresponding similarity
        poem_similarity_pairs = list(zip(poems, similarities))

        # Sort the pairs by similarity in descending order
        poem_similarity_pairs.sort(key=lambda x: x[1], reverse=True)

        count = 0
        # Print each pair on a new line
        for poem, similarity in poem_similarity_pairs:
            if similarity < 0.01:
                print(f"found {count} similar poems")
                break;
            else:
                count = count + 1
                print(f"{similarity:.2f}: {poem['entity']}")
                asyncio.run(send_telegram_message(poem['author'],poem['text'],'replace',image_path,poem['link_to_source'],poem['id'],poem['entity'],poem['rating'], similarity))
