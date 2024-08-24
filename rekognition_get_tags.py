import json
import boto3
import os
import sys

# Initialize the AWS Rekognition client
session = boto3.Session(profile_name='max')
client = session.client('rekognition', region_name='us-east-1')  

# Function to get image tags from AWS Rekognition
def get_image_tags_aws(image_path):
    with open(image_path, 'rb') as image_file:
        image_bytes = image_file.read()
    response = client.detect_labels(Image={'Bytes': image_bytes})
    labels = response['Labels']
    tags = [label['Name'] for label in labels]
    return tags

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
        tags = get_image_tags_aws(thumb_path)
        image_data['tags'] = tags
        
        print(f"Generated for image {thumb_path}, Tags: {tags}")

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
