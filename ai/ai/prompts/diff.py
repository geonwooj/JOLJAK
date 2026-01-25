
import json


SYSTEM = """
너는 한국 특허 문헌을 분석하는 AI 보조 분석가이다.
법률 판단이나 권리 범위 확정은 수행하지 않는다.
청구항 구성요소 단위로만 비교 분석한다.

규칙:
- 의미적으로 유사한 요소는 동일 요소로 간주한다.
- 신규성·진보성 판단은 하지 않는다.
- 출력은 반드시 JSON 형식만 허용한다.
"""
def build_user_idea_part(user_idea: str) -> str:
    if not user_idea.strip():
        return ""
    return f"[사용자 발명 개요]\n{user_idea.strip()}\n"

def build_prior_elements_part(prior_elements: list) -> str:
    if not prior_elements:
        return "[선행 특허의 청구항 구성 요소]\n(선행 특허 정보 없음)\n"
    return f"[선행 특허의 청구항 구성 요소]\n{json.dumps(prior_elements, ensure_ascii=False, indent=2)}\n"

def build_instruction_part() -> str:
    return """[분석 지시]
1. 구성 요소 단위로 비교하라.
2. 공통/차이 요소만 추출하라.

[출력 형식(JSON)]
{
  "common": ["공통 구성 요소"],
  "user_only": ["사용자 발명에만 존재하는 요소"],
  "prior_only": ["선행 특허에만 존재하는 요소"]
}
"""

def get_diff_prompt(user_idea: str, prior_elements: list) -> str:
  parts = [
        build_user_idea_part(user_idea),
        build_prior_elements_part(prior_elements),
        build_instruction_part()
    ]
  return "\n".join(p for p in parts if p.strip())
