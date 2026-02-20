import os
import json
import random
import numpy as np
from pathlib import Path
from tqdm import tqdm

from transformers import AutoModel
import torch

from models.KorPatBERT.korpat_tokenizer import Tokenizer


# ============================================================
# KorPatBERT Embedder
# ============================================================
class KorPatBERTEmbedder:
    def __init__(self):
        base = Path(__file__).parent

        self.tokenizer = Tokenizer(
            vocab_path=base / "models" / "KorPatBERT" / "pretrained" / "korpat_vocab.txt",
            cased=True
        )

        self.model = AutoModel.from_pretrained(
            base / "models" / "KorPatBERT" / "pytorch"
        )
        self.model.eval()

        print("[KorPatBERT] tokenizer + model loaded")

    def embed(self, text: str, max_len: int = 512) -> np.ndarray:
        token_ids, _ = self.tokenizer.encode(text, max_len=max_len)

        if not isinstance(token_ids, list):
            token_ids = list(token_ids)

        token_ids = token_ids[:max_len]

        input_ids = torch.tensor([token_ids], dtype=torch.long)
        attention_mask = (input_ids != 0).long()

        with torch.no_grad():
            outputs = self.model(
                input_ids=input_ids,
                attention_mask=attention_mask
            )

        last_hidden = outputs.last_hidden_state
        mask = attention_mask.unsqueeze(-1)

        emb = (last_hidden * mask).sum(dim=1) / mask.sum(dim=1)
        emb = emb.squeeze(0)

        emb = emb / (torch.norm(emb) + 1e-8)
        return emb.cpu().numpy()


# ============================================================
# 설정
# ============================================================
DATA_ROOT = "data/temp"
AI_DIR = os.path.join(DATA_ROOT, "ai")
BIGDATA_DIR = os.path.join(DATA_ROOT, "bigdata")
INFO_DIR = os.path.join(DATA_ROOT, "information")

RANDOM_SEED = 42
random.seed(RANDOM_SEED)


# ============================================================
# 유틸
# ============================================================
def load_patent_text(json_path: str) -> str:
    """
    claims + abstract 조합 (권장)
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    claims = data.get("claims", "")
    abstract = data.get("abstract", "")

    text = f"{abstract}\n{claims}".strip()

    if len(text) < 200:
        raise ValueError("Text too short")

    return text


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))


# ============================================================
# 비교 함수
# ============================================================
def compare_ai_with_field(ai_dir, target_dir, field_name, embedder):
    # 1️⃣ AI 특허 1개 랜덤 선택
    ai_files = [f for f in os.listdir(ai_dir) if f.endswith(".json")]
    ai_file = random.choice(ai_files)
    ai_path = os.path.join(ai_dir, ai_file)

    ai_text = load_patent_text(ai_path)
    ai_emb = embedder.embed(ai_text)

    print(f"\n[AI vs {field_name}]")
    print(f"AI 특허: {ai_file}")

    # 2️⃣ 대상 분야 로드 + 임베딩
    scores = []

    target_files = [f for f in os.listdir(target_dir) if f.endswith(".json")]

    for file in tqdm(target_files, desc=f"Comparing with {field_name}"):
        path = os.path.join(target_dir, file)

        try:
            text = load_patent_text(path)
            emb = embedder.embed(text)
            score = cosine_similarity(ai_emb, emb)

            scores.append((file, score))
        except Exception as e:
            print(f"Skip {file}: {e}")

    # 3️⃣ 결과 정렬
    scores.sort(key=lambda x: x[1], reverse=True)

    similarities = [s for _, s in scores]

    print("\nTop 10 most similar patents:")
    for pid, score in scores[:10]:
        print(f"{pid} | similarity = {score:.4f}")

    print("\nStatistics:")
    print(f" 평균 유사도: {np.mean(similarities):.4f}")
    print(f" 최대 유사도: {np.max(similarities):.4f}")
    print(f" 최소 유사도: {np.min(similarities):.4f}")
    print(f" 표준편차 : {np.std(similarities):.4f}")

    return scores


# ============================================================
# 실행
# ============================================================
if __name__ == "__main__":
    embedder = KorPatBERTEmbedder()

    compare_ai_with_field(AI_DIR, BIGDATA_DIR, "BigData", embedder)
    compare_ai_with_field(AI_DIR, INFO_DIR, "Information", embedder)