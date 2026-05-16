import json
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

def load_json_records(json_root, domain_order):
    records = []

    for domain in domain_order:
        folder = Path(json_root) / domain
        if not folder.exists():
            print(f"[WARN] missing folder: {folder}", flush=True)
            continue

        files = sorted(folder.glob("*.json"))
        print(f"[LOAD] {domain}: {len(files)} files", flush=True)

        for fp in files:
            with open(fp, "r", encoding="utf-8") as f:
                obj = json.load(f)

            clean_text = obj.get("clean_text", {})
            raw_text = obj.get("raw_text", {})

            rec = {
                "domain": domain,
                "doc_id": str(obj.get("id", fp.stem)),
                "path": str(fp),
                "abstract": clean_text.get("abstract", "") or raw_text.get("abstract", ""),
                "claims": clean_text.get("claims", "") or raw_text.get("claims", ""),
                "description": clean_text.get("description", "") or raw_text.get("description", ""),
            }
            records.append(rec)

    print(f"[INFO] total records = {len(records)}", flush=True)
    return records


def split_record_sections(record):
    return {
        "domain": record["domain"],
        "doc_id": record["doc_id"],
        "abstract": record.get("abstract", ""),
        "claims": record.get("claims", ""),
        "description": record.get("description", ""),
    }


def build_section_text_dict(records, section_order=("abstract", "claims", "description")):
    section_dict = {section: [] for section in section_order}

    for rec in records:
        for section in section_order:
            section_dict[section].append({
                "domain": rec["domain"],
                "doc_id": rec["doc_id"],
                "text": rec.get(section, ""),
            })

    return section_dict
    
    
    