import os
import boto3
from PIL import Image
from io import BytesIO

s3 = boto3.client('s3')
ssm = boto3.client('ssm')

def get_thumbnail_size():
    response = ssm.get_parameter(Name='/apps/ThumbnailCreator/ThumbnailSize', WithDecryption=True)
    size = response['Parameter']['Value']
    width, height = map(int, size.split('x'))
    return (width, height)


def create_thumbnail(image_path, size):
    with Image.open(image_path) as img:
        img.thumbnail(size)
        buffer = BytesIO()
        img.save(buffer, 'JPEG')
        buffer.seek(0)
        return buffer

def lambda_handler(event, context):
    size = get_thumbnail_size()

    for record in event['Records']:
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']
        
        response = s3.get_object(Bucket=bucket, Key=key)
        image_content = response['Body'].read()

        # Creating the thumbnail
        image_path = BytesIO(image_content)
        thumbnail = create_thumbnail(image_path, size)
        
        # Save the thumbnail back to S3
        thumbnail_key = 'thumbnails/' + os.path.basename(key)
        s3.put_object(Bucket=bucket, Key=thumbnail_key, Body=thumbnail, ContentType='image/jpeg')

        print('Thumbnail created and uploaded for:', key)

