
import json


SYSTEM = """
너는 여러 개의 청구항 초안을 비교하여
가장 일관되고 공통적인 내용을 선택하는 AI이다.
새로운 내용을 추가하지 않는다.
"""
def build_drafts_part(drafts: list) -> str:
    if not drafts:
        return "[초안 목록]\n(초안이 없습니다)\n"
    return f"[초안 목록]\n{json.dumps(drafts, ensure_ascii=False, indent=2)}\n"

def build_instruction_part() -> str:
    return """[지시]
1. 모든 초안에서 공통적으로 나타나는 구성 요소를 유지하라.
2. 일부 초안에만 있는 요소는 제거하라.
3. 하나의 청구항 세트로 재작성하라.

[출력 형식(JSON)]
{
  "final_claim_1": "",
  "final_dependent_claims": []
}
"""

def get_consensus_prompt(drafts: list) -> str:
  parts = [
        build_drafts_part(drafts),
        build_instruction_part()
    ]
  return "\n".join(parts)