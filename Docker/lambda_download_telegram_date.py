import json
import os, sys
from pyrogram import Client, errors
import boto3
from datetime import datetime
import json
from collections import OrderedDict
import tempfile

# Get the parent directory
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
# Add the parent directory to sys.path
sys.path.insert(0, parent_dir)
from rekognition_get_tags import get_image_tags_aws
from aws_translator import translate_word
from instagram_send import post_to_instagram_lang
from dotenv import load_dotenv

load_dotenv()

def extract_last_non_empty_line(text):
    # Split the text into lines and remove any trailing whitespace
    lines = text.strip().split('\n')
    
    # Remove empty lines
    lines = [line for line in lines if line.strip()]
    
    if lines:
        # Get the last non-empty line
        last_non_empty_line = lines[-1]
        # Get all text before the last non-empty line
        text_before_last_lines = lines[:-1]
        
        # Replace any line that contains both '[' and ']' with an empty line
        for i, line in enumerate(text_before_last_lines):
            if '[' in line and ']' in line:
                text_before_last_lines[i] = ''
                
        text_before_last = '\n'.join(text_before_last_lines)
        return text_before_last, last_non_empty_line
    else:
        return '', ''



def download_image(app, message):
    try:
            if message.photo:
                # Download the photo to a temporary file
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:                
                    app.download_media(message.photo.file_id, file_name=temp_file.name)
                    return temp_file.name
            else:
                raise ValueError(f"No photo found in the specified message {message}.")
    except errors.FloodWait as e:
        print(f"Flood wait: need to wait {e.value} seconds")
        time.sleep(e.value)
    except errors.BadRequest as e:
        print(f"Bad request: {str(e)}")
    except errors.MediaEmpty as e:
        print(f"Media is empty: {str(e)}")
    except errors.MediaInvalid as e:
        print(f"Invalid media: {str(e)}")
    except errors.MediaUnavailable as e:
        print(f"Media unavailable: {str(e)}")
    except errors.ServerError as e:
        print(f"Server error: {str(e)}")
    except errors.Unauthorized as e:
        print(f"Unauthorized access: {str(e)}")
    except errors.NetworkError as e:
        print(f"Network error: {str(e)}")
    except IOError as e:
        print(f"I/O error: {str(e)}")
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
    return None;


def lambda_handler():
    # Telegram setup
    channel_id_ru = os.getenv('TELEGRAM_CHANNEL_DP_ID_RU')
    channel_id_ua = os.getenv('TELEGRAM_CHANNEL_DP_ID_UA')
    channel_id_en = os.getenv('TELEGRAM_CHANNEL_DP_ID_EN')
    api_id =  os.getenv('TELEGRAM_API_ID')
    api_hash =  os.getenv('TELEGRAM_API_HASH')
    phone_number = os.getenv('PHONE_NUMBER')    

    app = Client("my_account", api_id=api_id, api_hash=api_hash, phone_number=phone_number)

    date_str_en = date_str_ua = date_str_ru = datetime.now()
    
    # Process updates to find the latest message from the specific channel
    last_message_text_ru = None
    last_message_text_ua = None
    last_message_text_en = None
    count = 0
    messages_ru = app.get_chat_history(channel_id_ru)
    messages_ua = app.get_chat_history(channel_id_ua)
    messages_en = app.get_chat_history(channel_id_en)
    url_ua = 'none'
    url_en = 'none'
    url_ru = 'none'
    tags_en = tags_ua = tags_ru = None
    temp_file_path = None

    for i in range(1):
        with app:        
            
            last_message_text_ru = next(messages_ru)
            temp_file_path = download_image(app, last_message_text_ru)
            if temp_file_path != None:  # Check if the message contains a photo
                tags_en = get_image_tags_aws(temp_file_path)
                if tags_en != None:
                    tags_ru = translate_word(', '.join(tags_en), "ru").strip().split(',')
                    tags_ua = translate_word(', '.join(tags_en), "uk").strip().split(',')
                    #print(f"temp_file: {temp_file_path}, tags: {tags_en}, tags: {tags_ru}, tags: {tags_ua} ")                

            date_str_ru = last_message_text_ru.date.strftime('%Y%m%d')
            text_ru, location_ru = extract_last_non_empty_line(last_message_text_ru.caption)
            if len(last_message_text_ru.caption_entities) > 1:
                url_ru = last_message_text_ru.caption_entities[1].url
            print(text_ru, location_ru, last_message_text_ru.date, url_ru, tags_ru)
    
            last_message_text_ua = next(messages_ua)
            date_str_ua = last_message_text_ua.date.strftime('%Y%m%d')
            text_ua, location_ua = extract_last_non_empty_line(last_message_text_ua.caption)
            
            if len(last_message_text_ua.caption_entities) > 1:
                url_ua = last_message_text_ua.caption_entities[1].url
            print(text_ua, location_ua, last_message_text_ua.date, url_ua, tags_ua)

            last_message_text_en = next(messages_en)
            date_str_en = last_message_text_en.date.strftime('%Y%m%d')
            text_en, location_en = extract_last_non_empty_line(last_message_text_en.caption)
            
            if len(last_message_text_en.caption_entities) > 1:
                url_en = last_message_text_en.caption_entities[1].url      
            print(text_en, location_en, last_message_text_en.date, url_en, tags_en)
            
    if temp_file_path != None:
        post_to_instagram_lang(temp_file_path, url_en, text_en, location_en, tags_en, 'eng')

    exit(0)
    # Set up S3 client
    session = boto3.Session(profile_name='max')
    s3 = session.client('s3', region_name='us-east-1')  

    bucket_name = 'daypicture.lemaxw.xyz'
    object_key = 'images.json'

    # Download the file from S3
    response = s3.get_object(Bucket=bucket_name, Key=object_key)
    content = response['Body'].read().decode('utf-8')
    data = json.loads(content)

    date_name= last_message_text_ua.date.strftime('%Y-%m-%d')
    image_name= f'images/{date_str_ua}.jpg'
    thumb_name= f'thumbnails/{date_str_ua}.jpg'
    filename_ua = f'poems/{date_str_ua}_ua.txt'
    filename_ru = f'poems/{date_str_ru}_ru.txt'
    filename_en = f'poems/{date_str_en}_en.txt'

    # Add a new element to the array (append to end of the list)
    
    data.append(
        {   
            "eventDate": f"{date_name}",
            "src": f"{image_name}",
            "thumb": f"{thumb_name}",
            "alt_ru": f"{location_ru}",
            "alt_ua": f"{location_ua}",
            "alt_en": f"{location_en}",
            "descriptions": {
                "ru": f"{filename_ru}",
                "ru_link": f"{url_ru}",
                "ua": f"{filename_ua}",
                "ua_link": f"{url_ua}",
                "en": f"{filename_en}",
                "en_link": f"{url_en}"                
            },
            "tags": {
                    "en": f"{tags_en}",
                    "ua": f"{tags_ua}",
                    "ru": f"{tags_ru}"                
            }
        }
    )
    
    # Convert the Python list back to a JSON string
    new_content = json.dumps(data, indent=4)

    print(f"new_content = {text_ru}, {text_ua}, {text_en}")

    
    
    # Upload the message to S3
    s3.put_object(Body=text_ua, Bucket=bucket_name, Key=filename_ua)
    s3.put_object(Body=text_ru, Bucket=bucket_name, Key=filename_ru)
    s3.put_object(Body=text_en, Bucket=bucket_name, Key=filename_en)
    s3.put_object(Body=new_content, Bucket=bucket_name, Key=object_key)

    return {
        'statusCode': 200,
        'body': json.dumps(last_message_text_ua.caption if last_message_text_ua else 'No messages found')
    }

lambda_handler()
