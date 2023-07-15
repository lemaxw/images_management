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

def extract_entity(text):    
    prompt=f'Summarize the following text in statement up to 77 characters:{text}'
    response = openai.Completion.create(
    engine="text-davinci-003", # Use "gpt-4" when it is available.
    prompt=prompt,
    max_tokens=77,
    temperature=0.3, # Higher values (closer to 1) make output more random; lower values make it more deterministic.
    )
    entity = response.choices[0].text
    if(len(entity) > 77):
        entity=remove_single_trailing_period(entity)
    if(len(entity) > 77):
        entity=remove_a(entity)
    if(len(entity) > 77):
        entity=remove_and(entity)
    if(len(entity) > 77):
        entity=remove_the(entity)
    return entity

#with open("/tmp/2.txt", 'r') as f:
#    print(extract_entity(f.read()))

