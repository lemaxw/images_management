# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /usr/src/app

# Set the timezone
ENV TZ=Asia/Jerusalem
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Copy the Python script into the container at /usr/src/app
COPY Docker/lambda_download_telegram.py ./
COPY Docker/my_account.session ./
COPY rekognition_get_tags.py ./
COPY aws_translator.py ./
COPY instagram_send.py ./

# Install any needed packages specified in requirements
RUN pip install --no-cache-dir pyrogram tgcrypto boto3 instagrapi geopy Pillow

# Run bot.py when the container launches
CMD ["python", "lambda_download_telegram.py"]