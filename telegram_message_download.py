from pyrogram import Client
from google_translator import translate_word
from openai_extract_entity import extract_entity
from db_upsert_entity import add_entry, is_id_exist
from utils import hash_alpha_chars, remove_numbers_from_end
from dotenv import load_dotenv

import os
import re
# load the environment variables from the .env file
load_dotenv()

api_id = os.getenv('TELEGRAM_API_ID')
api_hash = os.getenv('TELEGRAM_API_HASH')
channel_id = '@daypicture'  # The id or username of the channel from where to download photos

def remove_2_last_lines(text):
    # Split the text into lines
    lines = text.split('\n')
    # Remove empty lines
    lines = [line for line in lines if line.strip() != '']
    # Remove the last two non-empty lines
    lines = lines[:-2]
    # Join the lines back together
    return '\n'.join(lines)

def extract_author(author):
    # Split the text into lines
    lines = author.split('\n')
    # Remove empty lines
    lines = [line for line in lines if line.strip() != '']
    # Join the lines back together
    return ' '.join(lines)


def countReactions(reactions):
    if reactions:
        # Assuming `message` is a Message object
        total_reactions = 0
        for reaction in reactions:
            total_reactions += reaction.count
        return total_reactions

app = Client("my_account", api_id, api_hash)
def download_message():
    count = 0
    with app:
        for message in app.get_chat_history(channel_id):
            url=''
            translated_text=''
            entity=''
            reactions=0
            author=''
            if message.date < datetime.date(2022, 8, 1):
                break

            if message.caption_entities:
                if len(message.caption_entities) > 1:
                    first_entity = message.caption_entities[1]
                    url=first_entity.url
                    author=extract_author(message.caption[first_entity.offset:first_entity.offset+first_entity.length])
                    if message.reactions:
                      reactions=countReactions(message.reactions.reactions)
                else:
                    print(f"problematic: {message.caption_entities}")
                    continue
            else:
                print(f'missing entities: {message}')
                continue
            text = remove_2_last_lines(message.caption)
            text = remove_numbers_from_end(text)
            sha=hash_alpha_chars(text)
            if is_id_exist(sha):
                print(f"skkipping: {sha} for {text}")
            else:
                translated_text = translate_word(text, 'en')
                if translated_text:
                    entity = extract_entity(translated_text)
                else:
                    print(f'failed translate: {text}')
                    continue
                print(f"added {count}: {sha} for {entity}")
                #print(sha)
                #print(url)
                #print(author)
                #print(reactions)
                #print(translated_text)
                #print(entity)
                #print(message.date)

                add_entry(text, entity, translated_text, author, url, reactions, sha, message.date)
            count = count + 1

download_message()
