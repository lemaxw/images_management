from datetime import datetime, timedelta
import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError
from PIL import Image
import os

def prompt_next_weekdays():
    def find_next_tuesday():
        today = datetime.now()
        days_until_tuesday = (1 - today.weekday() + 7) % 7
        if days_until_tuesday == 0:
            days_until_tuesday += 7  # If today is Tuesday, choose the next one
        next_tuesday = today + timedelta(days_until_tuesday)
        return next_tuesday

    default_date = find_next_tuesday()
    date_input = input(f"Enter the start date (YYYY-MM-DD) [Default: {default_date.strftime('%Y-%m-%d')}]: ")

    if not date_input:
        start_date = default_date
    else:
        try:
            start_date = datetime.strptime(date_input, '%Y-%m-%d')
        except ValueError:
            print("Invalid date format. Using the default next Tuesday.")
            start_date = default_date
    return start_date

def resize_image(image_path, quality=85):
    with Image.open(image_path) as img:
        # Preserve original size
        new_size = img.size
        resized_img = img.resize(new_size, Image.LANCZOS)
        
        # Preserve EXIF data
        exif = img.info['exif'] if 'exif' in img.info else None
        
        resized_image_path = "/tmp/resized_" + os.path.basename(image_path)
        if exif:
            resized_img.save(resized_image_path, quality=quality, exif=exif)
        else:
            resized_img.save(resized_image_path, quality=quality)
        
        return resized_image_path

def should_resize(image_path, size_limit_mb=3):
    file_size_mb = os.path.getsize(image_path) / (1024 * 1024)
    return file_size_mb > size_limit_mb

def log_image_size(image_path, description):
    file_size_mb = os.path.getsize(image_path) / (1024 * 1024)
    print(f"{description} size: {file_size_mb:.2f} MB")

start_date = prompt_next_weekdays()
session = boto3.Session(profile_name='max')
s3_client = session.client('s3', region_name='us-east-1')

input_file = "/home/mpshater/images/input.txt"
delimiter = "|"
print(f"Start loop")

with open(input_file, "r") as file:
    for line in file:
        parts = line.strip().split(delimiter)
        location = parts[0]
        filename_local = parts[1]
                
        bucket_name = 'daypicture.lemaxw.xyz'
        key = start_date.strftime('images/%Y%m%d.jpg')

        log_image_size(filename_local, "Original image")

        if should_resize(filename_local):
            resized_image_path = resize_image(filename_local, quality=85)
            log_image_size(resized_image_path, "Resized image")
            if os.path.getsize(resized_image_path)  > os.path.getsize(filename_local):
                resized_image_path = filename_local
                print("original image smaller than resized, keep original")
            
        else:
            resized_image_path = filename_local

        print(f"Uploading {resized_image_path} to S3 bucket {bucket_name}")
        try:
            s3_client.upload_file(resized_image_path, bucket_name, key)
            print(f"File {resized_image_path} uploaded as {key} to {bucket_name} successfully")
        except FileNotFoundError:
            print("The file was not found at", resized_image_path)
        except NoCredentialsError:
            print("Credentials not available")
        except PartialCredentialsError:
            print("Incomplete credentials")
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                print("The specified bucket does not exist")
            else:
                print("Unexpected error:", e)
        
        if resized_image_path != filename_local:
            os.remove(resized_image_path)

        start_date = start_date + timedelta(days=1)
