import re

_latex_ocr = None

def _get_latex_ocr():
    """
    실제로 detect_equations()가 호출될 때만 LaTeXOCR 모델을 로드.
    텍스트 위주 PDF나 수식이 없는 PDF에서는 이 모델 로딩 자체를 건너뛴다.
    """
    global _latex_ocr
    if _latex_ocr is None:
        from rapid_latex_ocr import LaTeXOCR
        _latex_ocr = LaTeXOCR()
    return _latex_ocr


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