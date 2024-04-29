

from datetime import datetime, timedelta
import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError


def prompt_next_weekdays():
    def find_next_tuesday():
        today = datetime.now()
        # Calculate days until next Tuesday (weekday index 1)
        days_until_tuesday = (1 - today.weekday() + 7) % 7
        if days_until_tuesday == 0:
            days_until_tuesday += 7  # If today is Tuesday, choose the next one
        next_tuesday = today + timedelta(days=days_until_tuesday)
        return next_tuesday

    # Set the default date to the next Tuesday
    default_date = find_next_tuesday()
    date_input = input(f"Enter the start date (YYYY-MM-DD) [Default: {default_date.strftime('%Y-%m-%d')}]: ")

    # If no input is given, use the default date
    if not date_input:
        start_date = default_date
    else:
        # Try to parse the user's input
        try:
            start_date = datetime.strptime(date_input, '%Y-%m-%d')
        except ValueError:
            print("Invalid date format. Using the default next Tuesday.")
            start_date = default_date
    return start_date

start_date = prompt_next_weekdays()
s3_client = boto3.client('s3', region_name='us-east-1')  
# Open the file for reading
input_file = "/home/mpshater/images/input.txt"
# Define the delimiter as a regular expression pattern
delimiter = "|"

with open(input_file, "r") as file:

    # Loop through each line in the file
    for line in file:
        parts =  line.strip().split(delimiter)
        
        # Extract filename and statement
        location = parts[0]
        filename_local = parts[1]
                
        bucket_name = 'daypicture.lemaxw.xyz'
        filename = start_date.strftime('images/%Y%m%d.jpg')      

        # Upload the file to S3
 
        try:
            s3_client.upload_file(filename_local, bucket_name, filename)
            print(f"File {filename_local} uploaded as {filename} to {bucket_name} successfully")
        except FileNotFoundError:
            print("The file was not found at", filename_local)
        except NoCredentialsError:
            print("Credentials not available")
        except PartialCredentialsError:
            print("Incomplete credentials")
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                print("The specified bucket does not exist")
            else:
                print("Unexpected error:", e)

        start_date = start_date + timedelta(days=1)