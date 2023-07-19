import openai
from dotenv import load_dotenv
import os

# load the environment variables from the .env file
load_dotenv()

openai.api_key = os.getenv('OPENAI_API_KEY')

def remove_single_trailing_period(s):
    if s.endswith("."):
        return s[:-1]
    else:
        return s

def remove_a(s):
    s = s.replace("a ", "")
    s = s.replace("A ", "")
    return s

def remove_and(s):
    s = s.replace(" and ", ", ")
    return s

def remove_the(s):
    s = s.replace("the ", "")
    s = s.replace("The ", "")
    return s    

def request_with_retry(prompt_text, max_retries=3, delay=5):
    for attempt in range(max_retries):
        try:
            response = openai.Completion.create(
                engine="text-davinci-003",
                prompt=prompt_text,
                max_tokens=77
            )
            return response.choices[0].text.strip()

        except openai.error.APIConnectionError:
            if attempt < max_retries - 1:  # i.e. not the last attempt
                print(f"Error on attempt {attempt + 1}. Retrying in {delay} seconds...")
                time.sleep(delay)
                continue
            else:
                print("Max retries reached. Exiting.")
                raise  # Re-raise the last exception

def extract_entity(text):    
    prompt=f'Summarize the following text in statement up to 77 characters:{text}'
    entity = request_with_retry(prompt)
    if(len(entity) > 77):
        entity=remove_single_trailing_period(entity)
    if(len(entity) > 77):
        entity=remove_a(entity)
    if(len(entity) > 77):
        entity=remove_and(entity)
    if(len(entity) > 77):
        entity=remove_the(entity)
    return entity

#    print(extract_entity(f.read()))

#with open("/tmp/2.txt", 'r') as f:
