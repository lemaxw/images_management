FROM public.ecr.aws/lambda/python:3.8

WORKDIR /build

# Install zip
RUN yum install -y zip

# Copy your lambda function
COPY lambda_function.py ./

# Install Pillow
RUN pip install Pillow --target .

# Package everything into a zip file
RUN zip -r /tmp/lambda.zip .