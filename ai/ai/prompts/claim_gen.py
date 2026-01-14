SYSTEM = """
너는 한국 특허 명세서 작성 전문가이다.
법률 자문이나 권리 범위 확정은 하지 않는다.
청구항 문체를 엄격히 따른다.

규칙:
- 독립항은 하나의 문장
- 추상적 표현 금지
- 구성요소 나열 방식 사용
"""


def build_prompt(user_idea: str,
    diff: dict,
    prior_claims: dict) -> str:
    return f"""
[발명 개요]
{user_idea}

[선행 특허와의 차별 요소]
- 사용자 고유 요소: {diff["user_only"]}

[참고 선행 특허 청구항]
{prior_claims}

[지시]
차별 요소를 중심으로 다음을 작성하라.
1. 독립항 1개
2. 종속항 2~3개

[출력 형식(JSON)]
{{
  "claim_1": "",
  "dependent_claims": []
}}
"""
