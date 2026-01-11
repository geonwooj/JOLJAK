import re

def split_claims(claim_text: str):
    claims = {}
    parts = re.split(r'(청구항\s*\d+)', claim_text)

    for i in range(1, len(parts), 2):
        claims[parts[i].strip()] = parts[i + 1].strip()

    return claims
