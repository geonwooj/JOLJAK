import re

CLAIMS_START_PATTERNS = [
    r"\b청\s*구\s*항\b",
    r"\b청구항\b",
    r"\bclaims\b",
    r"\bwhat\s+is\s+claimed\s+is\b"
]

CLAIMS_END_PATTERNS = [
    r"\b발명의\s+상세한\s+설명\b",
    r"\b발명의\s+설명\b",
    r"\bdetailed\s+description\b",
    r"\bdescription\s+of\s+embodiments\b"
]


def fallback_extract_claims(full_text: str) -> str:
    text_lower = full_text.lower()

    start_idx = None
    for pat in CLAIMS_START_PATTERNS:
        m = re.search(pat, text_lower)
        if m:
            start_idx = m.start()
            break

    if start_idx is None:
        return ""

    end_idx = None
    for pat in CLAIMS_END_PATTERNS:
        m = re.search(pat, text_lower[start_idx:])
        if m:
            end_idx = start_idx + m.start()
            break

    if end_idx:
        return full_text[start_idx:end_idx].strip()
    return full_text[start_idx:].strip()