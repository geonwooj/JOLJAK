def is_low_quality_text(text: str) -> bool:
    if not text or len(text.strip()) < 300:
        return True

    hangul_ratio = sum(1 for c in text if '가' <= c <= '힣') / max(len(text), 1)
    return hangul_ratio < 0.15