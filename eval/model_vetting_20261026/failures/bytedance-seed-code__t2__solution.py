import re

def split_arabic_words(text: str) -> list[str]:
    return re.findall(r'[^\s،؛؟.,!?:…]+', text)
