SYSTEM = """
너는 여러 개의 청구항 초안을 비교하여
가장 일관되고 공통적인 내용을 선택하는 AI이다.
새로운 내용을 추가하지 않는다.
"""
def build_prompt(drafts: list) -> str:
    return f"""
[초안 목록]
{drafts}

[지시]
1. 모든 초안에서 공통적으로 나타나는 구성 요소를 유지하라.
2. 일부 초안에만 있는 요소는 제거하라.
3. 하나의 청구항 세트로 재작성하라.

[출력 형식(JSON)]
{{
  "final_claim_1": "",
  "final_dependent_claims": []
}}
"""