import boto3
import os

def is_inside_container():
    """
    Check if the script is running inside a container.
    You can use a more specific check based on your setup.
    """    
    isInside = os.path.exists('/.dockerenv') or os.path.exists('/usr/src/app')
    print(f"Running inside: {isInside}")
    return isInside

if is_inside_container():
    session = boto3.Session()  # Use default profile in container
else:
    session = boto3.Session(profile_name='max')  # Use 'max' profile on local machine

translate = session.client(service_name='translate', region_name='us-east-1', use_ssl=True)

# Initialize the AWS Rekognition client
def translate_word(word, target_language):
    try:
        result = translate.translate_text(
            Text=word,
            SourceLanguageCode="en",
            TargetLanguageCode=target_language
        )
        return result.get('TranslatedText')
            
    except (BotoCoreError, ClientError) as e:
        logger.error(f"Error translating word '{word}' to {target_language}: {str(e)}")
        return None  # You could also return a placeholder or raise an exception based on your needs

""" 
def translate_array(words):
    translations = {"Russian": [], "Ukrainian": []}
    
    for word in words:
        russian_translation = translate_word(word, "ru")
        ukrainian_translation = translate_word(word, "uk")
        
        translations["Russian"].append(russian_translation)
        translations["Ukrainian"].append(ukrainian_translation)
    
    return translations

# Example array of words
words = ["Tbilisi, Georgia", "Batumi, Georgia", "Beer Sheva, Israel", "Ushguli, Georgia", "language"]

# Translate the array
translated_words = translate_array(words)

print("Translations:")
for lang, translations in translated_words.items():
    print(f"{lang}: {translations}") """
