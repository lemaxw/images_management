import asyncio
from db_upsert_entity import get_poems
from telegram_send_msg import send_telegram_message
from sentences_comparator import get_similar_sentences

def publish_similarities(image, phrase, entities, poems):
    similarity_scores = get_similar_sentences(phrase, entities)

    # Pair statements with their corresponding similarity scores
    paired_statements = list(zip(poems, similarity_scores))

    # Sort the paired statements by similarity score in descending order
    sorted_statements = sorted(paired_statements, key=lambda x: x[1], reverse=True)

 
    count = 0
    # Print each pair on a new line
    for poem, similarity in sorted_statements:
        if similarity <= 0.02 or count == 10:
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

phrase = "seller keeps set of collorful ballons over it"
# Preprocess the image
image_path = "/home/mpshater/images/_MG_0088.jpg"
publish_similarities(image_path, phrase, entities_ua, poems_ua)
publish_similarities(image_path, phrase, entities_ru, poems_ru)


