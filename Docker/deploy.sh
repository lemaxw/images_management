#!/usr/bin/env bash
set -euo pipefail

# -----------------------------------------------------------------------------
# Prerequisites: 
#   - You should have AWS_ACCOUNT_ID defined in your environment (or in your .env).
#   - (Optionally) Define AWS_REGION and AWS_PROFILE if you want to override the defaults.
#     If you don't set them, REGION defaults to "us-east-1" and PROFILE defaults to "default".
#
# Example:
#   export AWS_ACCOUNT_ID=123456789012
#   export AWS_REGION=us-east-1
#   export AWS_PROFILE=max
#   ./deploy.sh
# -----------------------------------------------------------------------------
# Load environment variables from .env, if it exists in this folder
# -----------------------------------------------------------------------------
if [[ -f "~/.env" ]]; then
  # This strips out comments/empty lines and exports KEY=VALUE pairs
  export $(grep -v '^#' ~/.env | xargs)
fi
# Verify that AWS_ACCOUNT_ID is set
if [[ -z "${AWS_ACCOUNT_ID:-}" ]]; then
  echo "❌  ERROR: AWS_ACCOUNT_ID is not set. Please do:"
  echo "      export AWS_ACCOUNT_ID=your_account_id_here"
  exit 1
fi

# Fallbacks if not provided
AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_PROFILE="${AWS_PROFILE:-default}"

IMAGE_NAME="telegram-bot"
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

# 1) Build the Docker image
echo "🔨  Building Docker image '${IMAGE_NAME}'..."
docker build -f Docker/Dockerfile -t "${IMAGE_NAME}" .

# 2) Run it locally (so you can test before pushing). It pulls in your ~/.env and ~/.aws creds.
# echo "🏃  Running '${IMAGE_NAME}' locally to verify..."
# docker run --env-file ~/.env -v ~/.aws:/root/.aws "${IMAGE_NAME}"

# 3) Fetch ECR login password and log in
echo "🔑  Logging into ECR (${ECR_URI})..."
aws ecr get-login-password \
  --region "${AWS_REGION}" \
  --profile "${AWS_PROFILE}" \
  | docker login --username AWS --password-stdin "${ECR_URI}"

# 4) Tag the local image with the ECR repository:tag
echo "🏷️  Tagging image for ECR: ${ECR_URI}/${IMAGE_NAME}:latest"
docker tag "${IMAGE_NAME}:latest" "${ECR_URI}/${IMAGE_NAME}:latest"

# 5) Push to ECR
echo "📤  Pushing '${IMAGE_NAME}' to ECR..."
docker push "${ECR_URI}/${IMAGE_NAME}:latest"

echo "✅  Done! Image is now at ${ECR_URI}/${IMAGE_NAME}:latest"
