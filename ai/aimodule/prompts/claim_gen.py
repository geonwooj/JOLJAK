import json
from aimodule.utils.fewshot_loader import load_claim_generation_examples
from aimodule.config.prompt_config import DEFAULT_FIELD, DEFAULT_N_SHOTS, USE_FEW_SHOT

SYSTEM = """
너는 대한민국 특허 명세서 작성 전문가이다.
법률 자문이나 권리 범위 확정은 하지 않는다.
청구항 문체를 엄격히 따른다.

규칙:
- 독립항은 반드시 하나의 완전한 문장으로 구성한다.
- "포함하는 것을 특징으로 하는" 문구를 반드시 사용한다.
- 추상적·주관적 표현(우수한, 혁신적인, 획기적인 등) 절대 금지.
- 모든 구성요소는 "A와, B와, C를 포함하는" 형태로 나열한다.
- 입력된 정보만 기반으로 작성하며, 근거 없는 사실은 절대 추가하지 않는다.
- 검색된 다수의 선행 특허(Prior Arts)와 권리범위가 중첩되지 않도록 '사용자 고유 요소'를 중심으로 작성한다.
- 출력은 반드시 다음 JSON 형식만 허용되며, 다른 텍스트·설명·주석은 포함하지 않는다:
{
  "claim_1": "",
  "dependent_claims": []
}
"""

def build_fewshot_part(prior_arts: list, n_shots: int) -> str:
    """
    [핵심 수정] 기존 파일 로드 방식에서 검색 결과(prior_arts) 기반 동적 생성으로 변경
    """
    if not USE_FEW_SHOT or not prior_arts:
        return ""
    
    # 수정된 fewshot_loader 호출 (검색 결과를 전달)
    examples = load_claim_generation_examples(prior_arts=prior_arts, max_total=n_shots)
    
    fewshot_text = "### [학습용 청구항 작성 예시 (Dynamic Few-Shot)] ###\n"
    for ex in examples:
        fewshot_text += f"""[참고 선행 특허 요약]
{ex.get('abstract', '')[:300]}...

[참고 선행 청구항 구조]
{ex.get('claims', '')[:600]}...

────────────────────────\n"""
    return fewshot_text

def build_prior_arts_context(prior_arts: list) -> str:
    """검색된 선행 특허 정보를 분석 컨텍스트로 삽입"""
    if not prior_arts:
        return ""
    
    context = "[검색된 관련 선행 특허군 (Prior Arts Analysis)]\n"
    # 예제로 쓰인 것 외에 분석용으로 더 넓은 범위를 제공 (최대 5건)
    for i, art in enumerate(prior_arts[:5], 1):
        title = art.get('file', f'Patent_{i}').replace('.pdf', '')
        abstract = art.get('abstract', '요약 정보 없음')
        claims = art.get('claims', '청구항 정보 없음')[:300]
        
        context += f"<{i}. {title}>\n"
        context += f" - 기술 요약: {abstract}\n"
        context += f" - 선행 권리범위: {claims}...\n\n"
    return context

def build_diff_part(diff_elements: dict, user_idea: str) -> str:
    """차별 요소 및 아이디어 파츠"""
    user_only = json.dumps(diff_elements.get('user_only', diff_elements), ensure_ascii=False)
    return f"[사용자 발명 아이디어]\n{user_idea}\n\n[선행 특허와의 핵심 차별점]\n{user_only}\n"

def build_instruction_part() -> str:
    """지시 파츠"""
    return """[최종 지시]
1. 위 '학습용 청구항 작성 예시'의 문체와 '선행 특허군'의 권리범위를 분석하라.
2. 분석 결과와 중복되지 않도록 '핵심 차별점'을 제1항(독립항)의 필수 구성으로 포함하라.
3. 법적 효력이 있는 한국 특허 청구항 양식(제1항에 있어서, ~을 특징으로 하는 등)을 준수하라.
"""

def get_claim_gen_prompt(
    elements: dict,           
    diff_elements: dict,      
    user_idea: str = "",      
    prior_arts: list = None,  
    field: str = DEFAULT_FIELD,
    n_shots: int = DEFAULT_N_SHOTS,
    temperature: float = 0.3
) -> tuple[str, str]:
    """
    Dynamic Few-Shot이 적용된 청구항 생성 프롬프트 조립
    """
    # 1. 검색된 특허를 '학습 예시'로 변환 (Dynamic Few-Shot)
    fewshot_part = build_fewshot_part(prior_arts, n_shots)
    
    # 2. 검색된 특허를 '비교 분석 컨텍스트'로 삽입
    prior_context = build_prior_arts_context(prior_arts) if prior_arts else ""
    
    parts = [
        fewshot_part,
        prior_context,
        build_diff_part(diff_elements, user_idea),
        build_instruction_part()
    ]
    
    user_prompt = "\n".join(part for part in parts if part.strip())

    return SYSTEM, user_prompt