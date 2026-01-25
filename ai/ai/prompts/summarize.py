
SYSTEM = """
너는 한국 특허 문헌을 분석하는 AI 요약 보조 도구이다.
법률 해석이나 신규성 판단은 수행하지 않는다.
청구항 분석과 기술 비교를 위한 정보만 요약한다.
"""
def build_input_document_part(patent_text: str) -> str:
    text = patent_text.strip()
    if len(text) < 50:
        return "[입력 문서]\n(유효한 문서 내용이 매우 짧거나 없음)\n"
    # 너무 길면 앞뒤 일부만 → 실제로는 토큰 제한 고려하여 truncation 로직 추가 권장
    return f"[입력 문서]\n{text}\n"

def build_instruction_part() -> str:
    return """[요약 지시]
1. 기술 분야
2. 해결하려는 문제
3. 핵심 구성 요소
4. 주요 효과

[출력 형식(JSON)]
{
  "field": "",
  "problem": "",
  "components": [],
  "effects": []
}
"""

def get_summarize_prompt(patent_text: str) -> str:
  parts = [
        build_input_document_part(patent_text),
        build_instruction_part()
    ]
  return "\n".join(parts)