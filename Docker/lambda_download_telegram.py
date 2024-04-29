import json
import os
from pyrogram import Client
import boto3
from datetime import datetime
import json
from collections import OrderedDict


def lambda_handler():
    # Telegram setup
    channel_id_ru = os.getenv('TELEGRAM_CHANNEL_DP_ID_RU')
    channel_id_ua = os.getenv('TELEGRAM_CHANNEL_DP_ID_UA')
    api_id =  os.getenv('TELEGRAM_API_ID')
    api_hash =  os.getenv('TELEGRAM_API_HASH')
    phone_number = os.getenv('PHONE_NUMBER')

    app = Client("my_account", api_id=api_id, api_hash=api_hash, phone_number=phone_number)

    date_str_ua = date_str_ru = datetime.now()
    
    # Process updates to find the latest message from the specific channel
    last_message_text_ru = None
    last_message_text_ru = None
    with app:
        messages = app.get_chat_history(channel_id_ru)
        last_message_text_ru = next(messages)
        date_str_ru = last_message_text_ru.date.strftime('%Y%m%d')
  
  #      print(last_message_text_ru.caption, last_message_text_ru.date, last_message_text_ru.caption_entities[0])

   
        messages = app.get_chat_history(channel_id_ua)
        last_message_text_ua = next(messages)
        date_str_ua = last_message_text_ua.date.strftime('%Y%m%d')
        print(last_message_text_ua.caption, last_message_text_ua.date, last_message_text_ua.caption_entities[0])

        # Set up S3 client
        s3 = boto3.client('s3')
        bucket_name = 'daypicture.lemaxw.xyz'
        object_key = 'images.json'

        # Download the file from S3
        response = s3.get_object(Bucket=bucket_name, Key=object_key)
        content = response['Body'].read().decode('utf-8')
        data = json.loads(content)

        image_name= f'images/{date_str_ua}.jpg'
        filename_ua = f'poems/{date_str_ua}_ua.txt'
        filename_ru = f'poems/{date_str_ru}_ru.txt'

        # Add a new element to the array (append to end of the list)
        
        data.append(
            {   
                "src": f"{image_name}",
                "alt": "Description of Image",
                "descriptions": {
                    "ru": f"{filename_ru}",
                    "ukr": f"{filename_ua}"
                }
            }
        )
        
        # Convert the Python list back to a JSON string
        new_content = json.dumps(data, indent=4)

        
        
        # Upload the message to S3
        s3.put_object(Body=last_message_text_ua.caption, Bucket=bucket_name, Key=filename_ua)
        s3.put_object(Body=last_message_text_ru.caption, Bucket=bucket_name, Key=filename_ru)
        s3.put_object(Body=new_content, Bucket=bucket_name, Key=object_key)

    return {
        'statusCode': 200,
        'body': json.dumps(last_message_text_ua.caption if last_message_text_ua else 'No messages found')
    }

lambda_handler()
