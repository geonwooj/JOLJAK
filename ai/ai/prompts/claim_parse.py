# ai/prompts/claim_parse.py

SYSTEM = """
너는 특허 청구항 구조를 분석하는 도구이다.
내용의 옳고 그름은 판단하지 않는다.
"""
def build_claim_text_part(claim_text: str) -> str:
    text = claim_text.strip()
    if not text:
        return "[청구항]\n(청구항 텍스트 없음)\n"
    return f"[청구항]\n{text}\n"

def build_instruction_part() -> str:
    return """[지시]
1. 전제부 / 구성요소 / 한정요소로 분리하라.
2. 구성요소는 명사구 단위로 추출하라.

[출력 형식(JSON)]
{
  "preamble": "",
  "elements": [],
  "limitations": []
}
"""

def get_claim_parse_prompt(claim_text: str) -> str:
  parts = [
        build_claim_text_part(claim_text),
        build_instruction_part()
    ]
  return "\n".join(parts)