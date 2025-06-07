# Daily Image

This project streamlines the management of Telegram channels and an S3-hosted website used to publish curated images with matching poems.

![Workflow Diagram](desc.png)

## Features

- Uses AI to extract descriptions and locations from uploaded images
- Finds the most relevant poems in Russian and Ukrainian using semantic search
- Publishes posts (image + poem) to Telegram in multiple languages
- Uploads all high-resolution images to an S3-hosted website
- Automatically generates image thumbnails via AWS Lambda
- At the moment of Telegram publishing, downloads the selected poem and saves it to S3
- Archives images older than 1 year to S3 Glacier
- Republishes selected posts to Instagram