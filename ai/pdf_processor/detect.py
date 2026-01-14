import re

def detect_tables(text: str):
    return [
        m.group(0).strip()
        for m in re.finditer(r'표\s*\d+[\s\S]+?(?=\n\n|표\s*\d+|$)', text)
    ]


def detect_equations(text: str):
    return re.findall(r'수학식\s*\d+', text)
