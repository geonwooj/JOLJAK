import re

def normalize_text(text: str) -> str:
    text = text.replace('\u00a0', ' ')
    text = re.sub(r'([가-힣])\n([을를은는이가에의로])', r'\1\2', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'공개특허\s*10-\d{4}-\d{7}', '', text)
    text = re.sub(r'-\s*\d+\s*-', '', text)      
    text = re.sub(r'\n\s*[①-⑳]\s*', '\n', text)
    return text.strip()
