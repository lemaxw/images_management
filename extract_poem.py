import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from google_translator import translate_word
from openai_extract_entity import extract_entity
from db_upsert_entity import add_entry, is_id_exist
from datetime import datetime, timedelta
from utils import hash_alpha_chars, remove_numbers_from_end, randomize_array

def get_domain(url):
    # Use urlparse to break the url into its components
    parsed_url = urlparse(url)
    
    # The domain is available as the 'netloc' attribute
    domain = parsed_url.netloc
    return domain


def extract_poem(url):
    # Download the webpage
    response = requests.get(url)
    # Check to make sure the download was successful
    if response.status_code != 200:
        print(f"Failed to download page: {url}, status code: {response.status_code}")
        return [], [],

    # Parse the downloaded page with BeautifulSoup
    soup = BeautifulSoup(response.text, 'html.parser')

    # Find the main tag and class
    content_wrapper = soup.find('main', class_='content-wrapper')

    # Check if it exists
    if content_wrapper is None:
        print(f"Couldn't find main tag with class 'content-wrapper', for page {url}")
        return [],[]

    # Find the div with class 'container flex'
    container_flexe = content_wrapper.find('div', class_='container flexe')

    # Check if it exists
    if container_flexe is None:
        print(f"Couldn't find div with class 'container flexe', page: {url}")
        return [],[]

    # Find the div with class 'oscont'
    oscont = container_flexe.find('div', class_='oscont')

    # Check if it exists
    if oscont is None:
        print(f"Couldn't find div with class 'oscont' , page: {url}")
        return [],[]
        
    # Extract alt text from images
    alt_texts = [img['alt'] for img in oscont.find_all('img') if 'alt' in img.attrs]

    # Extract text from divs with class 'sttext'
    div_texts = [div.get_text(strip=True) for div in oscont.find_all('div', class_='sttext')]

    return alt_texts, div_texts


def extract_urls(url):
    # Download the webpage
    response = requests.get(url)
    # Check to make sure the download was successful
    if response.status_code != 200:
        print(f"Failed to download page: {url}, status code: {response.status_code}")
        return [], [],

    # Parse the downloaded page with BeautifulSoup
    soup = BeautifulSoup(response.text, 'html.parser')

    # Find the main tag and class
    content_wrapper = soup.find('main', class_='content-wrapper')

    # Check if it exists
    if content_wrapper is None:
        print(f"Couldn't find main tag with class 'content-wrapper', for page {url}")
        return [],[]

    # Find the div with class 'container flex'
    container_flexe = content_wrapper.find('div', class_='container flex-block')

    # Check if it exists
    if container_flexe is None:
        print(f"Couldn't find div with class 'container flexe', page: {url}")
        return [],[]

    # Find the div with class 'col-lg-8'
    col_lg_8 = container_flexe.find('div', class_='col-lg-8')

    # Check if it exists
    if col_lg_8 is None:
        print(f"Couldn't find div with class 'col-lg-8' , page: {url}")
        return [],[]

    # Find the div with class 'topics-list-kr'
    topics_list_kr = col_lg_8.find('div', class_='topics-list-kr')
   
    if topics_list_kr is None:
        print(f"Couldn't find div with class 'topics_list_kr' , page: {url}")
        return [],[]

    # Find the ul with class 'rows'
    ul_rows = topics_list_kr.find('ul', class_='rows')

    # Check if it exists
    if ul_rows is None:
        print("Couldn't find ul with class 'rows'")
        return None
    domain = get_domain(url)
    

    # Extract link and text from each a tag inside li tags
    #link_texts = [(a['href'], a.get_text(strip=True)) for a in ul_rows.find_all('a')]
    link_texts = [(f"https://{domain}{a['href']}") for a in ul_rows.find_all('a')]

    return link_texts

def extract_info(url):
    # Download the webpage
    response = requests.get(url)
    # Check to make sure the download was successful
    if response.status_code != 200:
        print(f"Failed to download page: {url}, status code: {response.status_code}")
        return [], [],

    # Parse the downloaded page with BeautifulSoup
    soup = BeautifulSoup(response.text, 'html.parser')

    # Find the main tag and class
    content_wrapper = soup.find('main', class_='content-wrapper')

    # Check if it exists
    if content_wrapper is None:
        print(f"Couldn't find main tag with class 'content-wrapper', for page {url}")
        return [],[]

    # Find the div with class 'container flex'
    container_flexe = content_wrapper.find('div', class_='container flex-block')

    # Check if it exists
    if container_flexe is None:
        print(f"Couldn't find div with class 'container flexe', page: {url}")
        return [],[]

    # Find the div with class 'col-lg-8'
    col_lg_8 = container_flexe.find('div', class_='col-lg-8')

    # Check if it exists
    if col_lg_8 is None:
        print(f"Couldn't find div with class 'col-lg-8' , page: {url}")
        return [],[]

    # Find the div with class 'topics-list-kr'
    topics_list_kr = col_lg_8.find('div', class_='topics-list-kr')
   
    if topics_list_kr is None:
        print(f"Couldn't find div with class 'topics_list_kr' , page: {url}")
        return [],[]

    # Find the div with class 'pagination'
    pagination = topics_list_kr.find('div', class_='pagination')
   
    if pagination is None:
        print(f"Couldn't find div with class 'pagination' , page: {url}")
        return [],[]


    # Find the ul with class 'rows'
    ul_rows = pagination.find('ul', class_='pagination')

    # Check if it exists
    if ul_rows is None:
        print("Couldn't find ul with class 'rows'")
        return None

    # Extract link and text from each a tag inside li tags
    link_texts = [(a['href']) for a in ul_rows.find_all('a')]
    link_texts.append(url)

    return link_texts


poets = ['ahmadulina-bella', 'pushkin-aleksandr','ahmatova-anna', 'rozhdestvenskiy-robert', 'esenin-sergey', 'dzhalil-musa', 
    'hayyam-omar', 'hayyam-omar', 'gamzatov-rasul', 'drunina-yuliya', 'chernyy-sasha', 'brodskiy-iosif', 'blok-aleksandr', 'okudzhava-bulat',
    'rubalskaya-larisa', 'polozkova-vera', 'pasternak-boris', 'nikitin-ivan', 'vysotskiy-vladimir', 'matveeva-novella', 'bunin-ivan',
    'fet-afanasiy', 'severyanin-igor', 'gumilev-nikolay', 'mayakovskiy-vladimir', 'belyy-andrey', 'zabolotskiy-nikolay', 'mandelshtam-osip',
    'harms-daniil', 'lermontov-mihail', 'balmont-konstantin', 'tarkovskiy-arseniy', 'voloshin-maksimilian', 'bryusov-valeriy', 'tyutchev-fedor',
    'annenskiy-innokentiy', 'surikov-ivan', 'vizbor-yuriy']

# Using the function
url = "https://poemata.ru/poets"

general_list=[];

poet_counts = 0
for poet in poets:
    poet_page = f"{url}/{poet}"
    all_pages = extract_info(poet_page)
    for page in all_pages:
        general_list = general_list + extract_urls(page)
    poet_counts = poet_counts + 1
    if poet_counts % 5 == 0:
        print(f"counts {poet_counts} poets, amount of poems:{len(general_list)}")


six_months_ago = datetime.now() - timedelta(days=180)
count = 0;
general_list = randomize_array(general_list)
for poem in general_list:
    author, div_texts = extract_poem(poem)
   # print(div_texts)
    if len(div_texts) > 0:
        text = remove_numbers_from_end(div_texts[0])
        sha=hash_alpha_chars(text)
        if is_id_exist(sha):
            print(f"skkipping: {sha} for {text}")
        else:
            translated_text = translate_word(text, 'en')
            if translated_text:
                entity = extract_entity(translated_text)
                if entity and entity != '':
                    add_entry(text, entity, translated_text, author[0], poem, 0, sha, six_months_ago)
                    count = count + 1
                    if count % 5 == 0:
                        print(f"counts {count} poems")
    else:
        print(f"failed extract poem {poem}")

print(f"added {poet_counts} poets and {counts} poems")
