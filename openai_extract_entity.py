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

def extract_first_n_words(t, n):
    return ' '.join(t.replace('\n',' ').split(' ')[:n])

text_prompt = 'Summarize in one short statement, the statement shouldn\'t exceed 77 characters, exclude from the statement a noun phrases:\n\n'

def request_with_retry(prompt_text, max_retries=3, delay=5):
    for attempt in range(max_retries):
        try:
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo-0613",
                messages=[
                  {"role": "user", "content": f"{prompt_text}"}
                ],
                max_tokens=77,
                temperature=0.5,
                top_p=1.0,
                frequency_penalty=0.0,
                presence_penalty=0.0
            )
            if text_prompt in response.choices[0].message.content.strip():
                print("got result identical to request, sleep and retry")
                time.sleep(delay)
                continue
            return response.choices[0].message.content.strip()
        except openai.RateLimitError as e:
            print(f"Rate limit exceeded: {e}")
            print("Please check your plan and billing details.")
            raise
        except openai.OpenAIError as e:
            print(f"An error occurred: {e}")
            raise
        except openai.APIConnectionError:
            if attempt < max_retries - 1:  # i.e. not the last attempt
                print(f"Error on attempt {attempt + 1}. Retrying in {delay} seconds...")
                time.sleep(delay)
                continue
            else:
                print("Max retries reached. Exiting.")
                raise  # Re-raise the last exception


def extract_entity(text):
    prompt=f'{text_prompt}{extract_first_n_words(text, 100)}'
    #print(prompt)
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

#with open("/tmp/1.txt", 'r') as f:    
#    print(extract_entity(f.read()))
