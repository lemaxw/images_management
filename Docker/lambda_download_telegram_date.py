import json
import os
from pyrogram import Client
import boto3
from datetime import datetime
import json
from collections import OrderedDict

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
        text_before_last = '\n'.join(lines[:-1])
        return text_before_last, last_non_empty_line
    else:
        return '', ''


def lambda_handler():
    # Telegram setup
    channel_id_ru = os.getenv('TELEGRAM_CHANNEL_DP_ID_RU')
    channel_id_ua = os.getenv('TELEGRAM_CHANNEL_DP_ID_UA')
    channel_id_en = os.getenv('TELEGRAM_CHANNEL_DP_ID_EN')
    api_id =  os.getenv('TELEGRAM_API_ID')
    api_hash =  os.getenv('TELEGRAM_API_HASH')
    phone_number = os.getenv('PHONE_NUMBER')

    app = Client("my_account", api_id=api_id, api_hash=api_hash, phone_number=phone_number)

    date_str_ua = date_str_ru = datetime.now()
    
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
    for i in range(3):
        with app:        
            
            last_message_text_ru = next(messages_ru)
            date_str_ru = last_message_text_ru.date.strftime('%Y%m%d')
            text_ru, location_ru = extract_last_non_empty_line(last_message_text_ru.caption)
            if len(last_message_text_ru.caption_entities) > 1:
                url_ru = last_message_text_ru.caption_entities[1]
            print(text_ru, location_ru, last_message_text_ru.date, url_ru)
    
            last_message_text_ua = next(messages_ua)
            date_str_ua = last_message_text_ua.date.strftime('%Y%m%d')
            text_ua, location_ua = extract_last_non_empty_line(last_message_text_ua.caption)
            
            if len(last_message_text_ru.caption_entities) > 1:
                url_ua = last_message_text_ua.caption_entities[1]
            print(text_ua, location_ua, last_message_text_ua.date, url_ua)

            last_message_text_en = next(messages_en)
            date_str_en = last_message_text_en.date.strftime('%Y%m%d')
            text_en, location_en = extract_last_non_empty_line(last_message_text_en.caption)
            
            if len(last_message_text_en.caption_entities) > 1:
                url_en = last_message_text_en.caption_entities[1]            
            print(text_en, location_en, last_message_text_en.date, url_en)

    # Set up S3 client
    s3 = boto3.client('s3')
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
            }
        }
    )
    
    # Convert the Python list back to a JSON string
    new_content = json.dumps(data, indent=4)

    
    
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
