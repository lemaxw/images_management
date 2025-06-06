from instagrapi import Client
import os, sys
import random
import requests
from instagrapi import Client
from instagrapi.types import Location
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
from geopy.distance import geodesic  # Import the geodesic distance function
import boto3
import json

def is_inside_container():
    """
    Check if the script is running inside a container.
    You can use a more specific check based on your setup.
    """    
    isInside = os.path.exists('/.dockerenv') or os.path.exists('/usr/src/app')
    print(f"Running inside: {isInside}")
    return isInside

if is_inside_container() == False:
    from dotenv import load_dotenv
    load_dotenv()

def parse_location_string(location_string: str) -> tuple[str, str] | tuple[None, None]:
    """
    Parses a location string in the format "City, Country" and returns
    the city and country as separate strings.  Handles potential errors.

    Args:
        location_string: The location string.

    Returns:
        A tuple (city, country) if successful, or (None, None) if parsing fails.
    """
    try:
        city, country = location_string.split(",", 1)  # Split on the first comma
        return city.strip(), country.strip()  # Remove leading/trailing spaces
    except ValueError:
        return None, None  # Return None, None if the format is incorrect

def create_instagram_caption(text: str, url: str, city: str, country: str, tags: list[str], has_coordinates: bool) -> str:
    """
    Formats the Instagram caption, handling location differently based on
    whether coordinates are available.
    """
    emojis = ["🎉", "🎃", "⭐", "🌟", "🌠", "🌌", "🗿"]
    selected_emoji = random.choice(emojis)

    parts = text.split("\n\n")
    if len(parts) < 2:
        return "Error: Text format is incorrect."

    poem_text = parts[0]
    # link_text = parts[1]
    author_location = parts[1]

    formatted_poem = f"{selected_emoji} {poem_text} {selected_emoji}"

    # try:
    #     link_text_clean = link_text[link_text.index("[") + 1:link_text.index("]")]
    # except ValueError:
    #     return "Error: Link text format is incorrect."
    # 
    # formatted_link = f"{link_text_clean} - {url}"

    formatted_link = f"Full poem - {url}"

    if has_coordinates:
        formatted_author_location = f"{author_location}"  # Only author if coordinates are used        
    else:
        formatted_author_location = f"{author_location}\n{city},{country}"  # Combine author and location        


    caption = f"{formatted_poem}\n\n{formatted_link}\n\n{formatted_author_location}"

    hashtag_string = "#" + "".join(c.lower() for c in author_location if c.isalnum())
    hashtag_string = hashtag_string + " #" + "".join(c.lower() for c in city if c.isalnum())
    hashtag_string = hashtag_string + " #" + "".join(c.lower() for c in country if c.isalnum()) + " "
    if tags:
        hashtag_string = hashtag_string + " ".join([f"#{tag}" for tag in tags[:20]])
    caption += "\n\n" + hashtag_string

    return caption

def get_coordinates_geopy(city: str, country: str) -> dict | None:
    """
    Uses geopy and OpenStreetMap Nominatim to get coordinates from a city and country.
    """
    try:
        geolocator = Nominatim(user_agent="instagram_poster")  # Use a descriptive user-agent
        location = geolocator.geocode(f"{city}, {country}", timeout=10) # Increased timeout

        if location:
            return {
                "name": f"{city}, {country}",  # Use the city/country as the name
                "lat": location.latitude,
                "lng": location.longitude,
                "address": location.address,  # Full address (might be useful)
                # external_id and external_id_source are not provided by Nominatim in
                # a readily usable format.  You *could* try to parse them from
                # location.raw, but it's not necessary for basic geotagging.
            }
        else:
            print(f"Warning: No coordinates found for {city}, {country}")
            return None

    except GeocoderTimedOut:
        print("Error: Geocoding timed out.  Try again later or use a different service.")
        return None
    except GeocoderUnavailable:
        print("Error: Geocoding service unavailable.  Check your internet connection.")
        return None
    except Exception as e:
        print(f"Error during geocoding: {e}")
        return None

def get_coordinates_instagrapi(latitude: float, longitude: float, client: Client, max_distance_miles: float = 10, min_distance_miles: float = 1 ) -> Location | None:
    """
    Finds the closest location using instagrapi within a maximum distance.
    """
    try:
        locations = client.location_search(latitude, longitude)
        if locations:
            print("Locations found by instagrapi:")
            closest_location = None
            min_distance = float('inf')  # Initialize with positive infinity

            for loc in locations:
                loc_dict = loc.dict()
                print(loc_dict)
                # Calculate the distance using geodesic distance
                distance = geodesic((latitude, longitude), (loc_dict['lat'], loc_dict['lng'])).miles

                print(f"  Distance: {distance:.2f} miles")

                if closest_location != None and distance <= max_distance_miles and min_distance_miles > distance:
                    print("found good enough, break")
                    break #prefer have location with highest amount of posts which is ranked higher

                if distance < min_distance and distance <= max_distance_miles:
                    min_distance = distance
                    closest_location = loc

            print("-" * 20)

            if closest_location and min_distance <= max_distance_miles:
                return closest_location  # Return the closest Location object
            else:
                print(f"Warning: Closest location found by instagrapi is more than {max_distance_miles} miles away.")
                return None

        else:
            print(f"Warning: No location found using instagrapi")
            return None
    except Exception as e:
        print(f"Error during location search using instagrapi: {e}")
        return None

def save_instagram_session(settings_data):
    if not is_inside_container():                
        with open("cookies.json", "w") as file:
            json.dump(settings_data, file)
    else:
        ssm = boto3.client("ssm")
        if ssm:
            ssm.put_parameter(
                Name="/apps/telegram-bot/INSTAGRAM_SESSION",
                Value=json.dumps(settings_data),
                Type="SecureString",
                Overwrite=True
            )
            print("Session saved to SSM Parameter Store.")
        else:
            print("Error: SSM client not available, can't save session.")

def post_to_instagram_lang(file_path: str, url: str, text: str, location_str: str, tags: list[str], lang: str):
    allow_instagram = os.getenv('ALLOW_INSTAGRAM')

    if not allow_instagram or allow_instagram != 'True':
        print("Error: ALLOW_INSTAGRAM isn't set, skip.")
        return

    if lang == 'eng':
        login_en = os.getenv('INSTAGRAM_VERSES_LOGIN_EN')
        pwd_en = os.getenv('INSTAGRAM_VERSES_PWD_EN')

    if not login_en or not pwd_en:
        print("Error: INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD environment variables must be set.")
        return
        
    create_new_session = False
    client = Client()
    try:
        if is_inside_container():            
            client.set_settings(json.loads(os.getenv('INSTAGRAM_SESSION')))
        elif os.path.exists("cookies.json"):
            client.load_settings("cookies.json")
        else:
            print("Error: No session file found, probably creating new session.")            
        if client.get_timeline_feed():
            print("✅ Session still valid!")
    except Exception as e:
        print(f"Error: failed to load session: {e}")
        create_new_session = True

    if create_new_session:
        print("Session expired, creating new session.")
        try:
            client = Client()
            client.login(login_en, pwd_en)
            print("✅ Successfully logged in to Instagram!")            
            save_instagram_session(client.get_settings())
        except Exception as e:
            print(f"Error: failed to login instagram: {e}")
            client.logout()
            return    
    
    post_to_instagram(file_path, url, text, location_str, tags, client)

    

def post_to_instagram(file_path: str, url: str, text: str, location_str: str, tags: list[str], client: Client):

    # Extract location information
    parts = text.split("\n\n")
    if len(parts) < 2:
        print("Error: Invalid text format for location extraction.")
        return
    author = parts[1]
    
    city, country = parse_location_string(location_str)
    location_dict = None
    has_coordinates = False

    if city and country:
        location_dict = get_coordinates_geopy(city, country)  # Use geopy        
        print(f"geopy location_dict = {location_dict}")
        if location_dict:            
            # Try to enhance with instagrapi:
            ig_location = get_coordinates_instagrapi(location_dict['lat'], location_dict['lng'], client, max_distance_miles=100) #Added max distance
            if ig_location: # Use instagrapi location if available
                has_coordinates = True
                location_dict = ig_location
            else:
                location_dict = None        

    caption = create_instagram_caption(text, url, city, country, tags, has_coordinates)

    if caption.startswith("Error"):
        print(caption)
        return
    print(f"Post: file_path: {file_path}, caption = {caption}, location_dict = {location_dict}")    
    
    try:
        if file_path.lower().endswith(('.jpg', '.jpeg', '.png')):
            # Create a new dictionary with ONLY the necessary keys:
            if location_dict:               
                media = client.photo_upload(file_path, caption, location=location_dict) # Pass cleaned dict
            else:
                media = client.photo_upload(file_path, caption) # Pass cleaned dict

        elif file_path.lower().endswith('.mp4'):
            # Create a new dictionary with ONLY the necessary keys:
            if location_dict:               
                media = client.video_upload(file_path, caption, location=location_dict) # Pass cleaned dict
            else:
                media = client.video_upload(file_path, caption) # Pass cleaned dict
        else:
            print("Error: Unsupported file type.")
            return
        print(f"Media uploaded successfully! Media ID: {media.id}")



    except Exception as e:
        print(f"An error occurred: {e}")
        
def test():
    # access_token = 'EACJMe1DE3f0BOZCHE61uGWXz5KZCRxbsEPOdlpW5isVnK5eUHKQynHn7roW5uZCie6MpNrMGGr1PiKiMv0IKJgmoVdHCPTX7Hyv9b9b3d6QpKpVnC6Xc8xwRcKUJKRcwqZC8OKKiwDxSzK90ZAYZAHQafQBprJ1ZASZBWZAJxYmr89PCL9HVrId9BuLXIwLnoZANxj8wZDZD'
    # access_token = 'EACJMe1DE3f0BOzhTOqeo1ZCSy2KX6zeoYTRWMBiHOdhdMwqkZCjZBJ8ZAUyef878YnnMHc6Lomoh2gZA8bbU1yHcCw7H3FjppJM6PgrMapQspkwuTZAyquJcZCxWFoTp8ErtUWEAZAfc5f53v04VfikHPjMUMu3MnKQdSSo3yS79MfPhKg7wW0YZAMzuYqj0ZC9J3ethvMd79fIOtTTRbIfk4ZBzyNp0AZDZD'
    access_token = 'EACJMe1DE3f0BO1ZBum61Xb2pRbMB4pSXPp4snHWTVy9M4wAMEvIa88T3l1h16s3lrsFKbJQlqWZCDDnkuJUOL3xQNbZAxrvhmsVumRxnZB9ZCQN0jdzyAUFnpxxRZAc4NwZA3mKxPk56LvdlOb1XwRtTiZAxfq86D6ZA1HV5QIn01qkgiZBU94lZChnr485egHXrh6yhEneIZC5AloSx8i6rZBZCXMRNxE4YEZD'
    ig_user_id = '17841473120084317'  # Your Instagram Business User ID
    # ig_user_id='511314911660080'

    create_url = f"https://graph.facebook.com/v22.0/{ig_user_id}/media"
    create_payload = {
        "image_url": "https://daypicture.lemaxw.xyz/images/20250328.jpg", 
        "caption": "Hello from my server!",
        "access_token": access_token
    }
    create_res = requests.post(create_url, data=create_payload)
    if create_res.status_code != 200:
        print("Error creating media container:", create_res.text)
        return

    print(f"create_res={create_res}")
    # 2. Publish the container
    creation_id = create_res.json().get("id")
    publish_url = f"https://graph.facebook.com/v22.0/{ig_user_id}/media_publish"
    publish_payload = {
        "creation_id": creation_id,
        "access_token": access_token
    }
    publish_res = requests.post(publish_url, data=publish_payload)
    if publish_res.status_code != 200:
        print("Error creating media container:", publish_res.text)
        return
    print(f"publish_res={publish_res}")


# --- Example Usage (Replace with your actual data) ---
if __name__ == '__main__':

    example_text = "FOLLOW thy fair sun, unhappy shadow!...\n\n[Full poem]\n\nThomas Campion"
    example_url = "https://www.example.com/fullpoem"  # URL for the bio
    example_file_path = "/home/mpshater/images/20241008_084807-2.jpg"  # Replace!
    example_tags = ["poetry", "ThomasCampion", "poem", "literature"]
    example_location = 'Beer Sheva, Israel'

    test()
    # login_en = os.getenv('INSTAGRAM_VERSES_LOGIN_EN')
    # pwd_en = os.getenv('INSTAGRAM_VERSES_PWD_EN')

    # if not login_en or not pwd_en:
    #     print("Error: INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD environment variables must be set.")

    # #print(f"{login_en}, {pwd_en}")
    # client = Client()
    # client.login(login_en, pwd_en)
    # Test posting (commented out to prevent accidental posts):
    # post_to_instagram(example_file_path, example_url, example_text, example_location, example_tags, client)
    # client.logout()

