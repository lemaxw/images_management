from googletrans import Translator

translator = Translator()
def translate_word(word, dest='ru'):
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