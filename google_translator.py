from googletrans import Translator

translator = Translator()


known_translations = {
    'uk': {
        'Tbilisi, Georgia': 'Тбілісі, Грузія',
        'Batumi, Georgia': 'Батумі, Грузія',
        'Beer Sheva, Israel': 'Беер-Шева, Ізраїль'
    },
    'ru': {
        'Tbilisi, Georgia': 'Тбилиси, Грузия',
        'Batumi, Georgia': 'Батуми, Грузия',
        'Beer Sheva, Israel': 'Беэр-Шева, Израиль'
    },
}

def translate_word(word, dest='ru'):

    if dest in known_translations:
        words = known_translations[dest]
        # Attempt to find the translated word by the word in the found hash
        if word in words:
            return words[word]        

    try:
        translation = translator.translate(word, dest)
        return translation.text
    except Exception as e:
        try:
            translation = translator.translate(word, dest)
            return translation.text
        except Exception as e:
            print(f'failed translate: {e}')  
    return ""

#text = translate_word('Опять в глуши, опять досуг', 'en')
#print(text)