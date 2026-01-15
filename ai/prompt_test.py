import json
from pathlib import Path
from ai.pipeline import GPTPipeline
from ai.utils.fewshot_loader import load_claim_generation_examples

gpt = GPTPipeline()

processed_dir = Path("data/processed")
json_files = list(processed_dir.glob("*.json"))

if not json_files:
    print("processed 폴더에 JSON 파일 없음 → pdf_test.py 먼저 실행하세요.")
    exit()

latest_json = max(json_files, key=lambda p: p.stat().st_mtime)
with open(latest_json, "r", encoding="utf-8") as f:
    input_data = json.load(f)

print(f"사용할 PDF JSON: {latest_json.name}")

user_idea = """
스마트폰과 연동되는 웨어러블 기기로 사용자의 운동 자세를 실시간 분석하고,
잘못된 자세를 즉시 교정해주는 AI 시스템입니다.
"""

diff_elements = {
    "user_only": [
        "개인 휴대형 웨어러블 센서",
        "실외 실시간 자세 교정",
        "스마트폰 앱 직접 연동"
    ]
}

examples = load_claim_generation_examples(
    subcategory="fitness",       
    max_per_file=5,      
    max_total=10                 
)
final_claim = gpt.generate_claim(
    elements=input_data,
    diff_elements=diff_elements,
    field="fitness",
    n_shots=3,
    temperature=0.3
)

print("최종 청구항 초안:")
print(json.dumps(final_claim, ensure_ascii=False, indent=2))