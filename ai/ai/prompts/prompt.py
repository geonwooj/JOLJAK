# ai/prompts/prompt.py

from typing import Dict
import json

from .summarize import get_summarize_prompt
from .claim_parse import get_claim_parse_prompt
from .diff import get_diff_prompt
from .claim_gen import get_claim_gen_prompt
from .consensus import get_consensus_prompt

from utils.fewshot_loader import load_claim_generation_examples

def assemble_pipeline_prompts(
    input_data: Dict, 
    user_idea: str,
    diff_elements: Dict,
    field: str = "fitness",
    n_shots: int = 3,
    temperature: float = 0.3
) -> Dict[str, str]:
    
    # 1단계: 요약 프롬프트
    summarize_p = get_summarize_prompt(input_data)
    
    # 2단계: 청구항 파싱 프롬프트
    parse_p = get_claim_parse_prompt(input_data.get("claims", "") or summarize_p)
    
    # 3단계: 차별점 분석 프롬프트
    diff_p = get_diff_prompt(parse_p, diff_elements)
    
    # few-shot 예제 로드
    examples = load_claim_generation_examples(field, max_examples=n_shots)
    
    # 4단계: 청구항 생성 프롬프트
    gen_p = get_claim_gen_prompt(
        parsed=parse_p,
        diff=diff_p,
        examples=examples,
        temperature=temperature
    )
    
    # 5단계: 합의 프롬프트
    consensus_p = get_consensus_prompt(gen_p)
    
    # 전체 조합 텍스트
    full_chain = f"""
[전체 파이프라인 프롬프트 미리보기 - 테스트용]

1. 요약 단계 프롬프트
──────────────────────
{summarize_p}

2. 청구항 파싱 단계 프롬프트
──────────────────────
{parse_p}

3. 차별점 분석 단계 프롬프트
──────────────────────
{diff_p}

4. 청구항 생성 단계 프롬프트 (few-shot 적용)
──────────────────────
{gen_p}

5. 합의/후처리 단계 프롬프트
──────────────────────
{consensus_p}
"""

    return {
        "summarize": summarize_p,
        "parse": parse_p,
        "diff": diff_p,
        "generate": gen_p,
        "consensus": consensus_p,
        "full_chain_preview": full_chain
    }