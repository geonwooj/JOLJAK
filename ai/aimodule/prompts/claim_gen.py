import json
from aimodule.utils.fewshot_loader import load_claim_generation_examples
from aimodule.config.prompt_config import DEFAULT_FIELD, DEFAULT_N_SHOTS, USE_FEW_SHOT

SYSTEM = """
너는 대한민국 특허 명세서 작성 전문가이다. 
반드시 아래의 '청구항 구조화 규칙'을 엄격히 준수하여 JSON으로 출력하라.

[청구항 구조화 규칙]
1. 제1항 (독립항): 
   - 발명의 핵심 구성요소들을 모두 포함하여 단일 문장으로 작성한다.
   - 마지막은 "...를 포함하는 것을 특징으로 하는 [발명의 명칭]."으로 끝낸다.

2. 제2항 이후 (종속항):
   - 반드시 "제1항에 있어서, ..." 또는 "제2항에 있어서, ..."와 같이 앞선 항을 인용하며 시작한다.
   - 독립항에 기재된 특정 구성을 구체화하거나, 부가적인 특징(예: 사출물 각도, 통신 방식 상세 등)을 추가한다.
   - 마지막은 "...를 특징으로 하는 [발명의 명칭]."으로 끝낸다.

3. 문체 유지:
   - 모든 항은 마침표 하나로 끝나는 하나의 문장이어야 한다.
   - '~하고', '~하며' 등의 법률적 문어체를 사용한다.

[출력 형식]
{
  "claim_1": "독립항 내용",
  "dependent_claims": [
    "제1항에 있어서, ...를 특징으로 하는 인공지능 자동 절전 시스템.",
    "제1항 또는 제2항에 있어서, ...를 특징으로 하는 인공지능 자동 절전 시스템."
  ]
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
    return """[최종 지시]
1. '선행 특허군'의 권리범위를 검토하여 이들과 겹치는 범용 기술은 과감히 생략하거나 전제부로 돌려라.
2. '핵심 차별점'에 기재된 요소가 발명의 해결수단으로서 어떻게 유기적으로 결합되는지 상세히 서술하라.
3. 특히, 기존 기술 대비 '사용자 아이디어'만이 갖는 구조적/기능적 특이점(예: 센서 분리 시 대응 로직, 특정 사출 구조 등)을 제1항의 마지막 특징점으로 강조하라.
4. 법적 효력이 있는 한국 특허 청구항 양식을 엄격히 준수하라.
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