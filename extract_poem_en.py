import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from openai_extract_entity import extract_entity
from db_upsert_entity import add_entry, is_id_exist, update_author_link
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
        return [], [], []

    # Parse the downloaded page with BeautifulSoup
    soup = BeautifulSoup(response.text, 'html.parser')

   # Find the relevant content div
    try:
        content_div = soup.find('div', class_='col-md-8 content m-0 p-3')
    except Exception as e:
        print(f"Error finding 'content' div: {e}")
        return [], [], []

    # Extract all 'p' tags within the content div
    try:
        p_tags = content_div.find_all('p')
    except Exception as e:
        print(f"Error finding 'p' tags: {e}")
        return [], [], []

    # Extract the text content of each 'p' tag
    p_contents = ''.join([str(p) for p in p_tags])
    p_html = ''.join([p.text for p in p_tags])
    # Find the div with class 'container flex'
    author_name = content_div.find('h2', class_='author_name').text   
    #print(author_name, p_contents, p_html)

    return author_name, p_contents, p_html


def extract_info(url):
    # Download the webpage
    response = requests.get(url)
    # Check to make sure the download was successful
    if response.status_code != 200:
        print(f"Failed to download page: {url}, status code: {response.status_code}")
        return [], [],

        
    # Parse the HTML and handle errors
    try:
        soup = BeautifulSoup(response.text, 'html.parser')
    except Exception as e:
        print(f"Error parsing HTML: {e}")
        exit()

    # Extract the title
    try:
        title_tag = soup.title
        title_content = title_tag.string if title_tag else "Title Not Found"
    except Exception as e:
        print(f"Error extracting title: {e}")
        title_content = "Title Extraction Error"  # Set a default in case of error

    # Find the 'div' element with the class 'works'
    try:
        works_div = soup.find('div', class_='works')
    except Exception as e:
        print(f"Error finding 'works' div: {e}")
        exit()  # Optional: you might only want to skip this block

    # Extract all the 'a' tags within the 'div'
    try:
        links = works_div.find_all('a')
    except Exception as e:
        print(f"Error finding links within 'works' div: {e}")
        exit()  # Optional: you might only want to skip this block

    # Create an array of the links 
    link_array = [f"{url}/../{link['href']}" for link in links]

    # Print the array
    # print(title_content, link_array)

    return title_content, link_array


poets = ['abercrombie_lascelles', 'alexander_cecil_frances', 'alexander_william', 'allingham_william', 'angelou_maya', 'arnold_matthew', 
        'auden_wystan_hugh', 'ayton_robert', 'baillie_joanna', 'barbauld_anna_laetitia', 'barbour_john', 'barham_richard', 'baring_maurice', 
        'barnard_anne', 'barnefield_richard', 'barnes_william', 'beaumont_francis', 'beaumont_john', 'beddoes_thomas_lovell', 'behn_aphra', 
        'belloc_hilaire', 'benet_stephen_vincent', 'betjeman_john', 'binyon_laurence', 'bishop_elizabeth', 'blake_william', 'blunden_edmund', 
        'blunt_wilfrid_scawen', 'boake_barcroft', 'bourdillon_francis_william', 'bowles_william_lisle', 'boyd_mark_alexander', 'brathwaite_kamau', 
        'breton_nicholas', 'bridges_robert', 'brittain_vera', 'bronte_anne', 'bronte_charlotte', 'bronte_emily', 'brooke_rupert', 'brown_thomas_edward', 'browne_william', 'browning_elizabeth_barrett', 'browning_robert', 'buchanan_robert', 'bunyan_john', 'burns_robert', 'byron_george_gordon', 'cambridge_ada', 'campbell_thomas', 'campion_thomas', 'carew_thomas', 'carey_henry', 'carroll_lewis', 'chalmers_patrick_reginald', 'chapman_george', 'chaucer_geoffrey', 'chesterton_gilbert_keith', 'cibber_colley', 'clare_john', 'clough_arthur', 'coleridge_hartley', 'coleridge_mary', 'coleridge_samuel_taylor', 'coleridge_sara', 'collins_john', 'collins_william', 'congreve_william', 'cone_helen_gray', 'constable_henry', 'cook_eliza', 'cory_william_johnson', 'cowley_abraham', 'cowper_william', 'crabbe_george', 'crane_harold_hart', 'crane_stephen', 'crashaw_richard', 'daniel_samuel', 'davenant_william', 'davidson_john', 'davies_john', 'davies_william_henry', 'dekker_thomas', 'dickinson_emily', 'dickinson_patric', 'dobell_eveline_jessie', 'dobell_sydney_thompson', 'dobson_henry_austin', 'donne_john', 'doudney_sarah', 'dove_rita', 'dowson_ernest', 'drayton_michael', 'drinkwater_john', 'drummond_william', 'dryden_john', 'dunbar_paul_laurence', 'dunbar_william', 'dyer_edward', 'dyer_katherine_doyley', 'edwardes_richard', 'eliot_george', 'eliot_thomas_stearns', 'elliot_jean', 'emerson_ralph_waldo', 'fanshawe_richard', 'farjeon_eleanor', 'favenc_ernest', 'fergusson_robert', 'fields_james_thomas', 'finch_anne', 'fitzgerald_edward', 'flecker_james_elroy', 'fletcher_giles', 'fletcher_john', 'fletcher_phineas', 'ford_john', 'frost_robert', 'gascoigne_george', 'gay_john', 'gilbert_william_schwenck', 'goldsmith_oliver', 'gordon_adam_lindsay', 'gore-booth_eva','gosse_edmund', 'graves_robert', 'gray_david', 'gray_thomas', 'greene_robert', 'greenwell_dora', 'gregory_augusta', 'grenfell_julian', 'greville_frances', 'greville_fulke', 'grimald_nicholas', 'guiterman_arthur', 'hammon_jupiter', 'hardy_thomas', 'harpur_charles', 'hawes_stephen', 'henley_william_ernest', 'henryson_robert', 'herbert_george', 'lord_herbert_of_cherbury', 'herrick_robert', 'heywood_thomas', 'hoccleve_thomas', 'hogg_james', 'hood_thomas', 'hopkins_gerard_manley', 'housman_alfred_edward', 'howard_henry', 'howitt_mary', 'hughes_ted', 'hulme_thomas_edward', 'hunt_james_leigh', 'ingelow_jean', 'james_i_of_scotland', 'johnson_lionel_pigot', 'jonson_ben', 'joyce_james', 'kavanagh_patrick', 'keats_john', 'kendall_henry', 'keyes_sidney', 'king_henry', 'kipling_rudyard', 'kominyakaa_yusef','lamb_charles', 'landon_letitia_elizabeth', 'landor_walter_savage', 'langland_william', 'larkin_philip', 'lawrence_david_herbert', 'lawson_henry', 'lee_laurie', 'lear_edward', 'letts_winifred', 'lindsey_vachel', 'lodge_thomas', 'longfellow_henry_wadsworth', 'lovelace_richard', 'lowell_amy', 'lowell_robert', 'lydgate_john', 'lyly_john', 'macaulay_thomas_babington', 'mackintosh_ewart', 'macniece_louis', 'mangan_james_clarence', 'mannyng_robert', 'de_la_mare_walter', 'marlowe_christopher', 'marvell_andrew', 'masefield_john', 'mccrae_john', 'meredith_george', 'mew_charlotte', 'meynell_alice', 'mickle_william_julius', 'millay_edna_st_vincent', 'milton_john', 'monroe_harriet', 'montgomerie_alexander', 'moore_marianne', 'moore_thomas', 'munday_anthony','nashe_thomas', 'nesbit_edith', 'newbolt_henry', 'noyes_alfred', 'obrien_john', 'oshaughnessy_arthur', 'ogilvie_william', 'oldys_william', 'owen_wilfred', 'pardlo_gregory', 'parkes_henry', 'paterson_andrew_barton', 'patmore_coventry', 'peacock_thomas_love', 'peele_george', 'picknell_marjorie', 'pilkington_laetitia', 'poe_edgar_allan', 'pope_alexander', 'prince_john_critchley', 'prior_matthew', 'quarles_francis', 'raleigh_walter', 'randolph_thomas', 'robinson_edwin_arlington', 'rollaston_thomas', 'rossetti_christina_georgina', 'rossetti_dante_gabriel', 'rowlands_richard', 'rosenberg_isaac', 'russell_george_william', 'sassoon_siegfried', 'scott_alexander', 'scott_walter', 'seeger_alan', 'seward_anna', 'sewell_george', 'shadwell_thomas', 'shakespeare_william', 'shelley_percy_bysshe', 'shorter_mary_dora_sigerson', 'sidney_philip', 'sims_george_robert', 'skelton_john', 'smith_tracy', 'sorley_charles', 'southey_robert', 'southwell_robert', 'spenser_edmund', 'speyer_leonora', 'stevenson_robert_louis', 'stevenson_william', 'storrie_agnes', 'suckling_john', 'swift_jonathan', 'swinburne_algernon_charles', 'sylvester_joshua','tate_nahum', 'teasdale_sara', 'tennyson_alfred', 'thackeray_william_makepeace', 'thomas_dylan', 'thomas_edward', 'thompson_francis', 'thomson_james', 'thorpe_rose_hartwick', 'todhunter_john', 'twain_mark', 'tynan_katharine', 'vaughan_henry', 'walcott_derek', 'warton_thomas', 'watson_william', 'webbe_charles', 'webster_john', 'wellesley_dorothy', 'wever_robert', 'wheatley_phillis', 'whitehead_william', 'whitman_walt', 'whittier_john_greenleaf', 'widdemer_margaret', 'wilde_oscar', 'wilcox_ella_wheeler', 'wither_george', 'wodehouse_pelham_grenville', 'wolfe_charles', 'wordsworth_william', 'wotton_henry', 'wurdeman_audrey', 'wyatt_thomas']



# Using the function
url = "https://englishverse.com/poets"

general_list=[];

poet_counts = 0
for poet in poets:
    poet_page = f"{url}/{poet}"
    poet, all_pages = extract_info(poet_page)

    for link in all_pages:
        update_author_link(link, poet, 'en')        
    

exit()

poet_counts = 0
for poet in poets:
    poet_page = f"{url}/{poet}"
    poet, all_pages = extract_info(poet_page)
    
    general_list = general_list + all_pages
    poet_counts = poet_counts + 1
    if poet_counts % 5 == 0:
        print(f"counts {poet_counts} poets, amount of poems:{len(general_list)}")
 #       break #!!!!!!!!!!!!!!!

#print(general_list)
six_months_ago = datetime.now() - timedelta(days=180)
count = 0
general_list = randomize_array(general_list)
for poem in general_list:
    author, div_texts, texts = extract_poem(poem)        
    if len(texts) > 0:
        sha=hash_alpha_chars(texts)
        if is_id_exist(sha):
            print(f"skiping: {sha} for {texts}")
        else:            
            entity = extract_entity(texts)
            if entity and entity != '':
                #print(entity, author, poem, 0, sha, six_months_ago)
                add_entry(div_texts, entity, texts, author[0], poem, 0, sha, six_months_ago, 'en')
                count = count + 1
                if count % 5 == 0:
                    print(f"counts {count} poems")
                    if count > 5000: 
                       break #!!!!!!!!!!!!!!
    else:
        print(f"failed extract poem {poem}")

print(f"added {poet_counts} poets and {count} poems")
