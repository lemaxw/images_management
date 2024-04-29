import os
import boto3
from PIL import Image
from io import BytesIO

s3 = boto3.client('s3')

def create_thumbnail(image_path):
    size = (128, 128)  # Define the size of the thumbnail

    with Image.open(image_path) as img:
        img.thumbnail(size)
        buffer = BytesIO()
        img.save(buffer, 'JPEG')
        buffer.seek(0)
        return buffer

def lambda_handler(event, context):
    for record in event['Records']:
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']
        
        response = s3.get_object(Bucket=bucket, Key=key)
        image_content = response['Body'].read()

        # Creating the thumbnail
        image_path = BytesIO(image_content)
        thumbnail = create_thumbnail(image_path)
        
        # Save the thumbnail back to S3
        thumbnail_key = 'thumbnails/' + os.path.basename(key)
        s3.put_object(Bucket=bucket, Key=thumbnail_key, Body=thumbnail, ContentType='image/jpeg')

        print('Thumbnail created and uploaded for:', key)

