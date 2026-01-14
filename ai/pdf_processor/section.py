import re

def extract_sections(full_text):
    text = re.sub(r'-\s*\d+\s*-', '', full_text)

    sections = {
        "title": "",
        "abstract": "",
        "claims": "",
        "description": "",
        "ipc": ""
    }

    # 제목
    title_match = re.search(
        r'발명의?\s*명칭\s*(.+?)(?:\n{2,}|\(57\)|요\s*약|【요약】)',
        text, re.DOTALL
    )
    if title_match:
        sections["title"] = title_match.group(1).strip()

    # 요약
    abstract_match = re.search(
        r'(요\s*약|【요약】)\s*(.+?)(?=청구범위|청구항|명\s*세\s*서|발명의?\s*설명)',
        text, re.DOTALL
    )
    if abstract_match:
        sections["abstract"] = abstract_match.group(2).strip()

    # 청구항
    claims_match = re.search(
        r'(청구범위|청구항\s*1)[\s\S]+?(?=발명의?\s*설명|기\s*술\s*분\s*야|배\s*경\s*기\s*술)',
        text
    )
    if claims_match:
        sections["claims"] = claims_match.group(0).strip()

    # 명세서
    desc_match = re.search(
        r'(기\s*술\s*분\s*야|배\s*경\s*기\s*술|발명의?\s*내용)[\s\S]+',
        text
    )
    if desc_match:
        sections["description"] = desc_match.group(0).strip()

    # IPC
    ipc_match = re.search(r'[A-H][0-9]{2}[A-Z]\s*\d+/\d+', text)
    if ipc_match:
        sections["ipc"] = ipc_match.group(0)

    return sections