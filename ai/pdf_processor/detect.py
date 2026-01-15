import re
from rapid_latex_ocr import LaTeXOCR
latex_ocr = LaTeXOCR()

def detect_tables(text: str):
    return [
        m.group(0).strip()
        for m in re.finditer(r'표\s*\d+[\s\S]+?(?=\n\n|표\s*\d+|$)', text)
    ]


def detect_equations(text: str):
    matches = re.finditer(r'수학식\s*\d+[\s\S]+?(?=\n\n|수학식\s*\d+|$)', text)
    parsed = []
    for m in matches:
        eq_text = m.group(0)
        parsed.append(eq_text)
    return parsed