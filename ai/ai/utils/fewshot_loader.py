from pathlib import Path
import json
from typing import List, Dict, Any

BASE_PATH = Path(__file__).resolve().parent.parent / "fewshots"

def load_claim_generation_examples(
    subcategory: str = "mechanical",
    max_examples: int = 4
) -> List[Dict[str, Any]]:
    path = BASE_PATH / f"{subcategory}.json"
    
    print(f"[fewshot_loader] 로드 시도: {path}") 
    
    if not path.exists():
        print(f"[fewshot_loader] 파일 없음: {path}")
        return []
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        loaded_count = len(data)
        print(f"[fewshot_loader] {loaded_count}개 예제 로드 완료: {subcategory}.json")
        return data[:max_examples]
    except json.JSONDecodeError as e:
        print(f"[fewshot_loader] JSON 파싱 오류 ({path}): {e}")
        return []
    except Exception as e:
        print(f"[fewshot_loader] 기타 오류: {e}")
        return []