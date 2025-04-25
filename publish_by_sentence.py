import asyncio
from db_upsert_entity import get_poems
from telegram_send_msg import send_telegram_message
from sentences_comparator import get_similar_sentences
from aws_translator import translate_word

def publish_similarities(image, phrase, entities, poems, location, word_link):
    similarity_scores = get_similar_sentences(phrase, entities)

    # Pair statements with their corresponding similarity scores
    paired_statements = list(zip(poems, similarity_scores))

    # Sort the paired statements by similarity score in descending order
    sorted_statements = sorted(paired_statements, key=lambda x: x[1], reverse=True)

 
    count = 0
    # Print each pair on a new line
    for poem, similarity in sorted_statements:
        if similarity <= 0.02 or count == 5:
            print(f"found {count} similar poems")
            break;
        else:
            count = count + 1
            print(f"{similarity:.2f}: {poem['entity']}")
            asyncio.run(send_telegram_message(poem['author'],poem['text'],location,image,poem['link_to_source'],poem['id'],poem['entity'],poem['rating'], similarity, word_link))


# List of potential texts
poems_ua =  get_poems('ua')
entities_ua = [poem['entity'] for poem in poems_ua if 'entity' in poem]
poems_ru =  get_poems('ru')
entities_ru = [poem['entity'] for poem in poems_ru if 'entity' in poem]
poems_en =  get_poems('en')
entities_en = [poem['entity'] for poem in poems_en if 'entity' in poem]

print(f"got {len(entities_ua)} entities for ua, {len(entities_ru)} entities for ru")

input_file = "/home/mpshater/images/input.txt"
# Define the delimiter as a regular expression pattern
delimiter = "|"

# Open the file for reading
with open(input_file, "r") as file:
    
    # Loop through each line in the file
    for line in file:
        
        parts =  line.strip().split(delimiter)
        
        # Extract filename and statement
        location = parts[0]
        filename = parts[1]
        statement = parts[2]

        # Print or do something with filename and statement
        print(f"Filename: {filename}, statement: {statement}")

        publish_similarities(filename, statement, entities_ua, poems_ua, translate_word(location, 'uk'), 'Повний твір')
        publish_similarities(filename, statement, entities_ru, poems_ru, translate_word(location, 'ru'), 'Полное произведение')
        publish_similarities(filename, statement, entities_en, poems_en, location, 'Full poem')