
import json

SYSTEM = """
너는 두 기술 간의 '신규성'을 판별하는 전문 특허 분석가이다.
유사한 단어에 속지 말고, 실제 구현 방식이나 제어 로직의 차이를 찾아내라.

[분석 규칙]
- 공통(Common): 선행 기술에서도 명시적으로 확인되는 기술 요소.
- 차별점(User_Only): 선행 기술에는 없거나, 선행 기술의 기능을 개선/변경한 사용자만의 고유 로직.
- 효과의 차이: 사용자 기술이 선행 기술보다 우위에 있게 만드는 결정적 요소를 키워드화 할 것.
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
1. 사용자 아이디어에서 '기존에 있던 것'과 '새로 추가된 것'을 엄격히 분리하라.
2. 특히 제어 흐름(알고리즘)이나 물리적 구조의 특이점에 집중하라.
3. 'user_only' 항목에는 청구항에 반드시 포함되어야 할 핵심 키워드 3~4개를 추출하라.

[출력 형식(JSON)]
{
  "common": [],
  "user_only": ["핵심 차별 요소 1", "핵심 차별 요소 2"],
  "differentiation_strategy": "선행 기술 대비 어떤 점을 강조하여 청구항을 써야 하는지에 대한 전략 가이드"
}
"""

def get_diff_prompt(user_idea: str, prior_elements: list) -> str:
  parts = [
        build_user_idea_part(user_idea),
        build_prior_elements_part(prior_elements),
        build_instruction_part()
    ]
  return "\n".join(p for p in parts if p.strip())
