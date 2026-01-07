import re

def normalize_ocr_typos(text: str) -> str:
    replacements = {
        "공개특히": "공개특허",
        "Al ": "AI ",
        " Al": " AI",
        "시권스": "시퀀스",
        "HO4": "H04"
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text


def normalize_text(text: str) -> str:
    text = text.replace('\u00a0', ' ')
    text = re.sub(r'([가-힣])\n([을를은는이가에의로])', r'\1\2', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()
