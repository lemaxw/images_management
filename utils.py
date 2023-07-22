
import re
import hashlib
import random

def randomize_array(array):
    random.shuffle(array)
    return array

def hash_alpha_chars(s):
    # Remove non-alphabet characters
    s = ''.join(c for c in s if c.isalpha())
    # Compute SHA-1 hash
    sha1 = hashlib.sha1(s.encode()).hexdigest()
    return sha1


def remove_numbers_from_end(string):
    return re.sub(r'\d+$', '', string)


def extract_author(string):
    return string.split('–', 1)[0]