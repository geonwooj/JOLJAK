import json
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

def normalize_text_basic(text: str) -> str:
    if not text:
        return ""

    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u00a0", " ")
    text = text.replace("\x00", " ")
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def phrase_to_pattern(phrase: str) -> str:
    phrase = normalize_text_basic(phrase)
    parts = re.split(r"\s+", phrase.strip())
    parts = [re.escape(x) for x in parts if x]

    if not parts:
        return ""

    return r"\s*".join(parts)


def remove_phrases(text: str, phrases):
    for ph in sorted(set(phrases), key=len, reverse=True):
        pattern = phrase_to_pattern(ph)
        if pattern:
            text = re.sub(pattern, " ", text, flags=re.IGNORECASE)

    return text


def _normalize_desc_text(text: str) -> str:
    if not text:
        return ""

    t = unicodedata.normalize("NFKC", text)
    t = t.replace("\u00a0", " ")
    t = t.replace("\x00", " ")
    t = t.replace("\r", "\n")

    lines = [ln.strip() for ln in t.split("\n")]
    lines = [ln for ln in lines if ln]

    return "\n".join(lines).strip()


def _extract_block_from_patterns(text: str, start_patterns, end_patterns=None, min_len: int = 30) -> str:
    if not text:
        return ""

    joined = _normalize_desc_text(text)
    if not joined:
        return ""

    start_pos = None
    for pat in start_patterns:
        m = re.search(pat, joined, flags=re.IGNORECASE)
        if m:
            start_pos = m.start()
            break

    if start_pos is None:
        return ""

    sub = joined[start_pos:]

    if end_patterns:
        end_pos = None
        for pat in end_patterns:
            m2 = re.search(pat, sub, flags=re.IGNORECASE)
            if m2:
                end_pos = m2.start()
                break

        block = sub[:end_pos].strip() if end_pos is not None else sub.strip()
    else:
        block = sub.strip()

    if len(block) < min_len:
        return ""

    return block


def extract_description_full_minus_background(text: str) -> str:
    start_patterns = [
        r"발명의\s*내용",
        r"해결하려는\s*과제",
        r"과제의\s*해결\s*수단",
        r"도면의\s*간단한\s*설명",
        r"도면에\s*대한\s*간단한\s*설명",
        r"발명을\s*실시하기\s*위한\s*구체적인\s*내용",
        r"발명의\s*실시를\s*위한\s*구체적인\s*내용",
        r"구체적인\s*실시예",
        r"실시예",
    ]

    block = _extract_block_from_patterns(
        text,
        start_patterns=start_patterns,
        end_patterns=None,
        min_len=30,
    )

    return block if block else _normalize_desc_text(text)


def cleanup_artifacts(text: str, section: str) -> str:
    text = normalize_text_basic(text)

    text = re.sub(r"\[\d{4}\]", " ", text)
    text = re.sub(r"등록특허\s*10-\d+", " ", text)
    text = re.sub(r"-\s*\d+\s*-", " ", text)

    if section == "claims":
        text = re.sub(r"청구항\s*\d+", " ", text)
        text = re.sub(r"제\s*\d+\s*항에\s*있어서", " ", text)

    text = re.sub(r"\s+", " ", text).strip()
    return text


def preprocess_section_text(
    text: str,
    section: str,
    domain: str,
    mode: str,
    section_stopwords,
    domain_extra_stopwords,
    description_view: str = "full_minus_background",
) -> str:
    if section == "description" and description_view == "full_minus_background":
        text = extract_description_full_minus_background(text)

    text = cleanup_artifacts(text, section)

    if mode == "x":
        return text

    common_cons = section_stopwords[section]["conservative"]
    common_strong = section_stopwords[section]["strong"]
    domain_cons = domain_extra_stopwords[domain][section]["conservative"]
    domain_strong = domain_extra_stopwords[domain][section]["strong"]

    if mode == "conservative":
        phrases = common_cons + domain_cons
    elif mode == "strong":
        phrases = common_cons + common_strong + domain_cons + domain_strong
    else:
        raise ValueError(f"Unknown mode: {mode}")

    text = remove_phrases(text, phrases)
    text = re.sub(r"\s+", " ", text).strip()

    return text


def preprocess_records_by_section(
    records,
    section_order,
    mode_order,
    section_stopwords,
    domain_extra_stopwords,
    description_view="full_minus_background",
):
    processed = {section: {mode: [] for mode in mode_order} for section in section_order}

    for rec in records:
        for section in section_order:
            for mode in mode_order:
                text = preprocess_section_text(
                    text=rec.get(section, ""),
                    section=section,
                    domain=rec["domain"],
                    mode=mode,
                    section_stopwords=section_stopwords,
                    domain_extra_stopwords=domain_extra_stopwords,
                    description_view=description_view,
                )

                processed[section][mode].append({
                    "domain": rec["domain"],
                    "doc_id": rec["doc_id"],
                    "text": text,
                })

    return processed