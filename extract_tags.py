import openai
from PIL import Image
import io
import os
import base64

from dotenv import load_dotenv
# load the environment variables from the .env file
load_dotenv()

openai.api_key = os.getenv('OPENAI_API_KEY')

def resize_image(image, size=(256, 256)):
    return image.resize(size, Image.LANCZOS)

def get_image_tags(image_path):
    # Open the image file
    with open(image_path, 'rb') as image_file:
        image = Image.open(image_file)
        image = resize_image(image)  # Resize the image
        image_bytes = io.BytesIO()
        image.save(image_bytes, format='PNG')
        image_data = image_bytes.getvalue()

    # Convert image to base64 for sending to the API
    image_base64 = base64.b64encode(image_data).decode('utf-8')

    # Prepare the prompt for GPT-4
    prompt = f"I have an image encoded in base64. The image depicts a natural landscape with various elements such as mountains, a river, greenery, and possibly other natural features. Please generate descriptive tags that accurately represent the contents of the image. Focus on identifying specific elements like mountains, river, vegetation, etc.: {image_base64}"

    # Call the OpenAI API
    client = openai.OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an assistant that generates image tags."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=50
    )

   # Extract and return the tags from the API response
    tags = response.choices[0].message.content.strip().split(',')
    return [tag.strip() for tag in tags]

    # Extract and return the tags from the API response

# Example usage
image_path = '/home/mpshater/images/20230813_194643.jpg'
tags = get_image_tags(image_path)
print("Generated Tags:", tags)
