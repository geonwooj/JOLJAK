from pathlib import Path
import json
from typing import List, Dict, Any
import random

BASE_PATH = Path(__file__).resolve().parent.parent / "fewshots"

def load_claim_generation_examples(
    subcategory: str = "fitness",
    max_per_file: int = 5,          # 파일당 최대 예제 수
    max_total: int = 15             # 전체 최대 예제 수
) -> List[Dict[str, Any]]:
    """
    ai/fewshots/{subcategory} 폴더 안의 모든 .json 파일을 읽어 예제 리스트 반환
    - fitness → ai/fewshots/fitness/*.json 전체 로드
    """
    folder_path = BASE_PATH / subcategory
    
    print(f"[fewshot_loader] 대상 폴더: {folder_path.absolute()}")
    
    if not folder_path.exists() or not folder_path.is_dir():
        print(f"[fewshot_loader] 폴더 없음 또는 디렉토리 아님: {folder_path}")
        print("해결: ai/fewshots/fitness/ 폴더를 만들고 JSON 파일을 넣어주세요")
        return []
    
    all_examples = []
    
    # 폴더 안 모든 .json 파일 순회
    for json_file in folder_path.glob("*.json"):
        print(f"  → 읽는 파일: {json_file.name}")
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                # 단일 객체이면 리스트로 변환
                if isinstance(data, dict):
                    data = [data]
                all_examples.extend(data[:max_per_file])
        except Exception as e:
            print(f"  → 파일 오류 ({json_file.name}): {e}")
    
    # 전체 예제 수 제한 (랜덤 섞기)
    if len(all_examples) > max_total:
        random.shuffle(all_examples)
        all_examples = all_examples[:max_total]
    
    total = len(all_examples)
    print(f"[fewshot_loader] 총 {total}개 예제 로드 완료 ({subcategory} 폴더)")
    
    return all_examples