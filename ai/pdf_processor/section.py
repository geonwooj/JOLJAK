# section.py — extract_sections 함수의 청구항 부분 교체

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

    # ── 청구항 — 수정된 로직 ────────────────────────────────────
    sections["claims"] = _extract_claims_section(text)

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


def _extract_claims_section(text: str) -> str:
    """
    청구항 섹션을 견고하게 추출.

    문제: 명세서 본문에 "청구항 N과 동일하게", "청구항 N에 기재된" 같은
    인용 표현이 있으면, 단순 re.search(r'청구항\\s*1')이 본문 중간의
    잘못된 위치에서 매치되어 명세서 전체를 청구항으로 오인할 수 있다.

    해결: "청구범위" 섹션 헤더를 1순위 기준점으로 삼는다.
    헤더가 없으면, "청구항 1." 패턴 중에서도 줄 시작(MULTILINE)에 있고
    뒤따르는 텍스트가 실제 청구항 종료 신호(발명의 설명 등) 전까지
    "청구항 N." 패턴이 연속적으로 반복되는 블록만 인정한다.
    """
    # 1순위: "청구범위" 헤더 기준 (가장 안정적)
    header_match = re.search(r'청\s*구\s*범\s*위', text)

    end_pattern = r'(?=발명의?\s*설명|기\s*술\s*분\s*야|배\s*경\s*기\s*술|도\s*면\s*$)'

    if header_match:
        start = header_match.start()
        remainder = text[start:]
        end_match = re.search(end_pattern, remainder)
        if end_match:
            return remainder[:end_match.start()].strip()
        # 종료 신호를 못 찾으면, 청구항 섹션이 비정상적으로 길 위험이 있으므로
        # 안전장치로 최대 길이를 제한 (일반적인 청구항 섹션은 수천~수만자 이내)
        MAX_CLAIMS_LEN = 30000
        return remainder[:MAX_CLAIMS_LEN].strip()

    # 2순위: 헤더가 없는 경우 — "청구항 1." 이 줄 시작에서 등장하는 지점부터
    # (본문 인용구는 보통 "청구항 N"+조사가 붙고, 줄 시작에 오더라도
    #  바로 뒤에 "."이 오지 않는 경우가 많으므로 "청구항 1." 형태로 좁힘)
    first_claim_match = re.search(r'^청구항\s*1\s*[\.\)]', text, re.MULTILINE)
    if first_claim_match:
        start = first_claim_match.start()
        remainder = text[start:]
        end_match = re.search(end_pattern, remainder)
        if end_match:
            return remainder[:end_match.start()].strip()
        MAX_CLAIMS_LEN = 30000
        return remainder[:MAX_CLAIMS_LEN].strip()

    return ""