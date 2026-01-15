# ai/prompts/claim_gen.py

import json
from ai.utils.fewshot_loader import load_claim_generation_examples
from ai.config.prompt_config import DEFAULT_FIELD, DEFAULT_N_SHOTS, USE_FEW_SHOT

SYSTEM = """
너는 한국 특허 명세서 작성 전문가이다.
법률 자문이나 권리 범위 확정은 하지 않는다.
청구항 문체를 엄격히 따른다.

규칙:
- 독립항은 반드시 하나의 완전한 문장으로 구성한다.
- "포함하는 것을 특징으로 하는" 문구를 반드시 사용한다.
- 추상적·주관적 표현(우수한, 혁신적인, 획기적인 등) 절대 금지.
- 모든 구성요소는 "A와, B와, C를 포함하는" 형태로 나열한다.
- 입력된 정보만 기반으로 작성하며, 근거 없는 사실은 절대 추가하지 않는다.
- 출력은 반드시 다음 JSON 형식만 허용되며, 다른 텍스트·설명·주석은 포함하지 않는다:
{
  "claim_1": "",
  "dependent_claims": []
}
"""

def get_claim_gen_prompt(
    elements: dict,
    diff_elements: dict,
    field: str = DEFAULT_FIELD,
    n_shots: int = DEFAULT_N_SHOTS,
    temperature: float = 0.3
) -> tuple[str, str]:
    """
    청구항 생성 프롬프트 생성
    - few-shot은 여기서만 로드
    - temperature는 llm_client에 전달용으로 함께 반환
    """
    fewshot_text = ""
    if USE_FEW_SHOT:
        examples = load_claim_generation_examples(field, max_per_file=n_shots)
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

    user_prompt = f"""
{fewshot_text}

[현재 발명 개요]
{elements.get('title', '')}
{elements.get('abstract', '')}

[선행 특허와의 차별 요소]
사용자 고유 요소: {json.dumps(diff_elements.get('user_only', []), ensure_ascii=False)}

[참고 선행 특허 청구항]
{json.dumps(elements.get('claims_structured', {}), ensure_ascii=False, indent=2)}

[지시]
위 예시 문체를 정확히 따르며 차별 요소를 중심으로 청구항을 작성하라.
독립항 1개 + 종속항 2~4개 생성.
"""

    return SYSTEM, user_prompt