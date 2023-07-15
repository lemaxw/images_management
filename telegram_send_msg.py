import os
import asyncio

from dotenv import load_dotenv
from aiogram import Bot, types
from image_manipulation import resize_image
from io import BytesIO
from aiogram.utils.exceptions import CantParseEntities, RetryAfter, NetworkError
from aiohttp import ClientConnectorError


# load the environment variables from the .env file
load_dotenv()

token=os.getenv('TELEGRAM_ADMIN_TOKEN') 
channel_id = os.getenv('TELEGRAM_CHANNEL_ID')
print (f'token={token}, channel_id={channel_id}')

bot = Bot(token=token)

async def send_telegram_message(poet,poem,location,photo_path_or_url,url,id,entity,rate, similarity):    

    img = resize_image(photo_path_or_url, 10000)
    photo_data = BytesIO()
    img.save(photo_data, format='JPEG')
    photo_data.seek(0)
    found_caption=False
    while(found_caption == False):
        caption = f'<i>{poem}</i>\n\n'  # Add line break for the next line
        caption += f'<a href="{url}">{poet}</a>\n\n'
        caption += location
        caption += f'\nentity:{entity}'
        caption += f'\nrate:{rate}'
        caption += f'\nid:{id}'
        caption += f'\nsimilarity:{similarity:.2f}'
        
        if(len(caption) > 1076):
            poem = poem[:(int(len(poem)/2))] + "\n..."
        else:
            found_caption=True
    
    max_retries = 5
    for i in range(max_retries):
        try:
            await bot.send_photo(chat_id=channel_id, photo=photo_data, caption=caption, parse_mode=types.ParseMode.HTML)
            break
        except CantParseEntities as e:
            print(f"Error while sending message: {str(e)}")
            break
        except RetryAfter as e:
            print(f"Flood control exceeded. Retrying in {e.timeout} seconds.")
            await asyncio.sleep(e.timeout)
        except NetworkError as e:            
            if i < max_retries - 1:  # i is zero indexed
                print(f"Network error: {str(e)}. Retrying in 5 seconds.")
                await asyncio.sleep(5)
                continue
            else:
                print(f"Network error: {str(e)}. Maximum retries exceeded.")
                break

    await bot.close()