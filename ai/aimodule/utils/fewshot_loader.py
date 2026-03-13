from pathlib import Path
import json
from typing import List, Dict, Any

# 기존 경로 설정 유지 (하위 호환성)
BASE_PATH = Path(__file__).resolve().parent.parent / "fewshots"

def load_claim_generation_examples(
    subcategory: str = "fitness",   # 기존 인자 유지 (에러 방지)
    max_per_file: int = 5,          # 기존 인자 유지 (에러 방지)
    max_total: int = 3,             # 실제 사용할 예제 수
    prior_arts: List[Dict[str, Any]] = None  # 신규 추가: 검색 결과
) -> List[Dict[str, Any]]:
    """
    [Dynamic Few-Shot] 검색된 유사 특허(prior_arts)를 
    GPT가 학습할 수 있는 예제 리스트 형태로 변환합니다.
    """
    
    # 1. 만약 검색 결과(prior_arts)가 들어오지 않았다면 빈 리스트 반환
    if not prior_arts:
        print(f"[fewshot_loader] 참고할 검색 결과가 없습니다. (요청 분야: {subcategory})")
        return []

    all_examples = []
    
    # 2. 검색 결과(prior_arts)를 순회하며 예제 형식으로 재구성
    # 리스트 슬라이싱을 통해 max_total만큼만 추출
    for art in prior_arts[:max_total]:
        example = {
            "abstract": art.get("abstract", ""),
            "claims": art.get("claims", "")
        }
        all_examples.append(example)

    total = len(all_examples)
    print(f"[fewshot_loader] 총 {total}개의 유사 특허를 Dynamic Few-Shot 예제로 구성 완료")
    
    return all_examples