import re

def split_claims(claim_text: str):
    """
    "청구항 N에 있어서" 같은 본문 인용구를 분리 지점으로 오인하지 않도록
    줄 시작 + negative lookahead 패턴 사용.
    """
    claims = {}
    pattern = re.compile(r"(^청구항\s*\d+(?!\s*에\s*있어서))", re.MULTILINE)
    parts = pattern.split(claim_text)

    for i in range(1, len(parts), 2):
        key = parts[i].strip()
        claims[key] = parts[i + 1].strip()

    return claims