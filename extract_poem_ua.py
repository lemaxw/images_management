import requests
from bs4 import BeautifulSoup
from google_translator import translate_word
from openai_extract_entity import extract_entity
from db_upsert_entity import add_entry, is_id_exist, update_author
from datetime import datetime, timedelta
from utils import hash_alpha_chars, remove_numbers_from_end, randomize_array, extract_author
import time

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
}


def extract_poem(url):
    # Download the webpage
    delay = 5
    try:
        response = requests.get(url, headers=headers, timeout=10)  # set timeout to 10 seconds
        response.raise_for_status()  # This will raise an HTTPError if the HTTP request returned an unsuccessful status code

    except requests.exceptions.RequestException as e:  # This is the base class for all Requests' exceptions
        print(f"Error fetching URL: {e}, {delay} seconds...")
        time.sleep(delay)
        return [], [],

    except requests.exceptions.HTTPError:
        print("HTTP Error occurred.")
        return [], [],

    except requests.exceptions.ConnectionError:
        print("Error connecting to the server.")
        return [], [],

    except requests.exceptions.Timeout:
        print("The request timed out.")
        return [], [],

    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return [], [],
        
    # Parse the downloaded page with BeautifulSoup
    soup = BeautifulSoup(response.text, 'html.parser')

    # Find the author 
    entry_header = soup.find('h1', class_='entry-title')
    author = extract_author(entry_header.text)

    # Find the div with class 'container flex'
    poem_text = soup.find('div', class_='entry-content poem-text')

    # Check if it exists
    if poem_text is None:
        print(f"Couldn't find div with class 'poem_text', page: {url}")
        return [],[]

    poem = ""
     # Find all top-level <p> tags
    top_level_p_tags = [tag for tag in poem_text.find_all('p', recursive=False)]
    
  #  print (top_level_p_tags)
    # Extract the text from these tags
    poem = ""
    for tag in top_level_p_tags:
        tag_text = tag.get_text().strip()  # Using strip() to consider tags with whitespace as empty too.
#        print(tag_text, 'end')
        if not tag_text:
            break
        if '___' in tag_text:
            break
        poem = poem + tag_text
    
    return author, poem


def extract_urls(url):
    # Download the webpage

    response = requests.get(url, headers=headers)
    # Check to make sure the download was successful
    if response.status_code != 200:
        print(f"Failed to download page: {url}, status code: {response.status_code}")
        return [], [],

    # Parse the downloaded page with BeautifulSoup
    soup = BeautifulSoup(response.text, 'html.parser')
    
    posts_container = soup.find('div', class_='posts-container')

    # Check if it exists
    if posts_container is None:
        print(f"Couldn't find div with class 'posts_container' , page: {url}")
        return [],[]

    # Find the div with class 'topics-list-kr'
    topics_list_kr = posts_container.find_all('div', class_='entry-title')
   
    if len(topics_list_kr) == 0:
        print(f"Couldn't find div with class 'topics_list_kr' , page: {url}")
        return [],[]

    # Find the ul with class 'rows'
    link_texts = [a.find('a')['href'] for a in topics_list_kr]
    return link_texts


poets = ['taras-shevchenko', 'lesya-ukrayinka','ivan-franko', 'volodymyr-sosyura', 'dmytro-pavlychko', 'marusya-churaj', 
    'pavlo-glazovyj', 'leonid-glibov', 'oleksandr-oles', 'myhajlo-stelmah', 'vasyl-stus', 'vasyl-symonenko', 'lina-kostenko', 'grygorij-skovoroda',
    'maksym-rylskyj', 'myhajl-semenko', 'pavlo-tychyna', 'oleg-olzhych', 'olena-teliga', 'andrij-malyshko']

# Using the function
url = "https://virshi.com.ua"


general_list=[];

poet_counts = 0
for poet in poets:
    poet_page = f"{url}/{poet}"
    general_list = general_list + extract_urls(poet_page)
    poet_counts = poet_counts + 1
    if poet_counts % 5 == 0:
        print(f"counts {poet_counts} poets, amount of poems:{len(general_list)}")


six_months_ago = datetime.now() - timedelta(days=180)
count = 0;
general_list = randomize_array(general_list)
for poem in general_list:
    author, text = extract_poem(poem)
    if text:
    # print(div_texts)
        sha=hash_alpha_chars(text)
        if is_id_exist(sha, dbname='ua'):
            print(f"skkipping: {sha} for {text}")
        else:
            translated_text = translate_word(text, 'en')
            if translated_text:
                entity = extract_entity(translated_text)
                if entity:
                    add_entry(text, entity, translated_text, author, poem, 0, sha, six_months_ago, dbname='ua')
                    #print(text, entity, translated_text, author, poem, 0, sha, six_months_ago)
                    count = count + 1
                    if count % 20 == 0:
                        print(f"counts {count} poems")

print(f"added {poet_counts} poets and {count} poems")
