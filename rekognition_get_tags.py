import json
import boto3
import botocore
import logging
import os
import sys
from aws_translator import translate_word

# Initialize the AWS Rekognition client

def is_inside_container():
    """
    Check if the script is running inside a container.
    You can use a more specific check based on your setup.
    """    
    isInside = os.path.exists('/.dockerenv') or os.path.exists('/usr/src/app')
    print(f"Running inside: {isInside}")
    return isInside

if is_inside_container():
    session = boto3.Session()  # Use default profile in container
else:
    session = boto3.Session(profile_name='max')  # Use 'max' profile on local machine

client = session.client('rekognition', region_name='us-east-1')  

# Function to get image tags from AWS Rekognition
def get_image_tags_aws(image_path):
    try:
        # Read the image file
        with open(image_path, 'rb') as image_file:
            image_bytes = image_file.read()

        # Call AWS Rekognition
        response = client.detect_labels(Image={'Bytes': image_bytes})
        
        # Extract labels from response
        labels = response['Labels']
        tags = [label['Name'] for label in labels]
        return tags

    except FileNotFoundError:
        logging.error(f"File not found: {image_path}")
        return None
    except PermissionError:
        logging.error(f"Permission denied: {image_path}")
        return None
    except botocore.exceptions.NoCredentialsError:
        logging.error("AWS credentials not found.")
        return None
    except botocore.exceptions.PartialCredentialsError:
        logging.error("Incomplete AWS credentials.")
        return None
    except botocore.exceptions.EndpointConnectionError:
        logging.error("Failed to connect to AWS endpoint.")
        return None
    except botocore.exceptions.ClientError as e:
        logging.error(f"Client error: {e.response['Error']['Message']}")
        return None
    except KeyError:
        logging.error("Unexpected response structure.")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred: {str(e)}")
        return None


# Function to process images and update the JSON file
def process_images_and_update_json(directory):
    json_file_path = os.path.join(directory, 'images.json')

    # Load the JSON list from a file
    with open(json_file_path, 'r', encoding='utf-8') as file:
        image_list = json.load(file)

    # Process each image in the list
    for image_data in image_list:
        thumb_path = os.path.join(directory, image_data['thumb'])
        
        # Get tags for the image
        tags_en = get_image_tags_aws(thumb_path)
        if tags_en != None:
            tags_ru = translate_word(', '.join(tags_en), "ru").strip().split(',')
            tags_ua = translate_word(', '.join(tags_en), "uk").strip().split(',')
        image_data['tags'] = {}
        image_data['tags']['en'] = tags_en
        image_data['tags']['ru'] = tags_ru
        image_data['tags']['ua'] = tags_ua
        
        print(f"Generated for image {thumb_path}, Tags: {tags_en}, {tags_ru}, {tags_ua}")

    # Save the updated JSON list back to a file
    with open(json_file_path, 'w', encoding='utf-8') as file:
        json.dump(image_list, file, ensure_ascii=False, indent=4)

    print("Tags added and JSON updated successfully.")


# Main function
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py <directory>")
        sys.exit(1)

    directory = sys.argv[1]
    process_images_and_update_json(directory)
