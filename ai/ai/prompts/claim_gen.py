import json
from ..utils.fewshot_loader import load_claim_generation_examples
from ..config.prompt_config import DEFAULT_FIELD, DEFAULT_N_SHOTS, USE_FEW_SHOT

SYSTEM = """
너는 한국 특허 명세서 작성 전문가이다.
법률 자문이나 권리 범위 확정은 하지 않는다.
청구항 문체를 엄격히 따른다.

규칙:
- 독립항은 하나의 문장
- 추상적 표현 금지
- 구성요소 나열 방식 사용
"""


def build_prompt(
    elements: dict,  
    diff_elements: dict,  
    examples: list  
) -> str:
    fewshot_text = ""
    if USE_FEW_SHOT:
        if not examples:  
            examples = load_claim_generation_examples(DEFAULT_FIELD, DEFAULT_N_SHOTS)
        
        for ex in examples:
            fewshot_text += f"""[예시 입력]
발명 개요: {ex.get('user_idea', '')}
차별 요소: {json.dumps(ex.get('diff', {}), ensure_ascii=False)}

[참고 선행 청구항]
{ex.get('prior_claims', '')}

[모범 출력]
{json.dumps(ex.get('output', {}), ensure_ascii=False, indent=2)}

────────────────────────
"""

    user_prompt = f"""{fewshot_text}

[발명 개요]
# user_idea는 pipeline에서 별도 전달되지 않음 - diff_elements나 elements에서 유추 (테스트용 하드코딩 제거)
# 실제: prompt_test.py의 user_idea를 elements로 대체 가정

[선행 특허와의 차별 요소]
- 사용자 고유 요소: {diff_elements.get("user_only", [])}

[참고 선행 특허 청구항]
{elements}  # dict 문자열화

[지시]
차별 요소를 중심으로 다음을 작성하라.
1. 독립항 1개
2. 종속항 2~3개

위 예시 문체를 정확히 따라라.

[출력 형식(JSON)]
{{
  "claim_1": "",
  "dependent_claims": []
}}
"""

    return user_prompt
