import os, json, random, pickle
import numpy as np
from pathlib import Path
from tqdm import tqdm

from transformers import AutoModel
import torch
from models.KorPatBERT.korpat_tokenizer import Tokenizer

# ============================================================
# KorPatBERT Embedder (당신 코드 그대로)
# ============================================================
class KorPatBERTEmbedder:
    def __init__(self):
        base = Path(__file__).parent
        self.tokenizer = Tokenizer(
            vocab_path=base / "models" / "KorPatBERT" / "pretrained" / "korpat_vocab.txt",
            cased=True
        )
        self.model = AutoModel.from_pretrained(base / "models" / "KorPatBERT" / "pytorch")
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
            outputs = self.model(input_ids=input_ids, attention_mask=attention_mask)

        last_hidden = outputs.last_hidden_state
        mask = attention_mask.unsqueeze(-1)

        emb = (last_hidden * mask).sum(dim=1) / mask.sum(dim=1)
        emb = emb.squeeze(0)

        emb = emb / (torch.norm(emb) + 1e-8)  # L2 normalize
        return emb.cpu().numpy()


# ============================================================
# Utils
# ============================================================
def l2norm_rows(X: np.ndarray) -> np.ndarray:
    return X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-12)

def cosine_stats(vecs: np.ndarray, name: str, max_pairs: int = 200_000):
    """
    vecs: (N,D) already L2-normalized
    샘플링으로 pairwise 통계(메모리 폭발 방지)
    """
    N = vecs.shape[0]
    if N < 2:
        print(f"[{name}] not enough vectors")
        return

    # 무작위 pair 샘플링
    rng = np.random.default_rng(42)
    m = min(max_pairs, N*(N-1)//2)
    i = rng.integers(0, N, size=m)
    j = rng.integers(0, N, size=m)
    mask = (i != j)
    i, j = i[mask], j[mask]

    sims = np.sum(vecs[i] * vecs[j], axis=1)  # dot = cosine
    qs = np.quantile(sims, [0.01, 0.05, 0.50, 0.95, 0.99])
    print(f"\n[{name}] N={N}, sampled_pairs={len(sims)}")
    print(f"  mean={sims.mean():.6f}  std={sims.std():.6f}  min={sims.min():.6f}  max={sims.max():.6f}")
    print(f"  q01={qs[0]:.6f} q05={qs[1]:.6f} q50={qs[2]:.6f} q95={qs[3]:.6f} q99={qs[4]:.6f}")

def apply_centering(vecs: np.ndarray):
    mu = vecs.mean(axis=0, keepdims=True)
    vc = vecs - mu
    vc = l2norm_rows(vc)
    return vc, mu

def apply_remove_top_pcs(centered_vecs: np.ndarray, k: int = 2):
    """
    centered_vecs: (N,D) centered된 상태(정규화 전/후 상관없지만, 보통 centered 후 normalize 하기 전이 더 정석)
    여기서는 centered_vecs가 이미 normalized돼 있어도 PC 제거는 동작합니다.
    """
    # SVD로 상위 PC
    # centered_vecs가 (N,D)면 Vt는 (D,D) or (N,D) 형태. 여기선 Vt[:k]를 PC로 사용
    U, S, Vt = np.linalg.svd(centered_vecs, full_matrices=False)
    PCs = Vt[:k]  # (k,D)

    # 각 벡터에서 PC 성분 제거: X - (X @ PCs.T) @ PCs
    proj = (centered_vecs @ PCs.T) @ PCs
    v2 = centered_vecs - proj
    v2 = l2norm_rows(v2)
    return v2, PCs

def load_text_from_json(path: str, mode: str = "claims_only") -> str:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    claims = data.get("claims", "") or ""
    abstract = data.get("abstract", "") or ""

    if mode == "claims_only":
        text = claims.strip()
    elif mode == "abs_claims":
        text = f"{abstract}\n{claims}".strip()
    else:
        raise ValueError("mode must be 'claims_only' or 'abs_claims'")

    return text

def collect_json_paths(root_dirs, limit=800, seed=42):
    all_paths = []
    for d in root_dirs:
        if not os.path.isdir(d):
            continue
        for fn in os.listdir(d):
            if fn.endswith(".json"):
                all_paths.append(os.path.join(d, fn))
    random.Random(seed).shuffle(all_paths)
    return all_paths[:limit]


# ============================================================
# Main
# ============================================================
if __name__ == "__main__":
    # === 설정 ===
    DATA_ROOT = "data/temp"
    AI_DIR = os.path.join(DATA_ROOT, "ai")
    BIGDATA_DIR = os.path.join(DATA_ROOT, "bigdata")
    INFO_DIR = os.path.join(DATA_ROOT, "information")

    SAMPLE_N = 400          # 200~800 사이로 시작 추천 (너무 크면 임베딩 생성 시간이 늘어남)
    TEXT_MODE = "claims_only"  # "claims_only" 권장(지금 목적에 맞게)
    REMOVE_PC_K = 2         # 상위 1~3부터 실험 (2 추천)
    SAVE_CALIB = True       # mu, PCs 저장

    # === 진단용 비교 문장(원하시면 여기만 바꿔 끼우면 됩니다) ===
    text_A = "모델은 입력 특징을 벡터로 변환해 표현을 만든다. 학습은 손실 함수를 최소화하도록 파라미터를 업데이트한다."
    text_B = "형사피해자는 법률이 정하는 바에 의하여 당해 사건의 재판절차에서 진술할 수 있다. 모든 국민은 주거의 자유를 침해받지 아니한다."

    embedder = KorPatBERTEmbedder()

    # 1) 랜덤 문서 샘플 → 임베딩
    paths = collect_json_paths([AI_DIR, BIGDATA_DIR, INFO_DIR], limit=SAMPLE_N)
    vecs = []
    used = 0
    for p in tqdm(paths, desc="Embedding sampled docs"):
        try:
            t = load_text_from_json(p, mode=TEXT_MODE)
            if len(t) < 80:  # 너무 짧은 건 스킵
                continue
            v = embedder.embed(t)
            vecs.append(v)
            used += 1
        except Exception:
            continue

    vecs = np.vstack(vecs)  # (N,768), 이미 normalize됨
    print(f"\n[DEBUG] collected vectors: {vecs.shape}")

    # (1) 원본 코사인 분포
    cosine_stats(vecs, "RAW")

    # 2) centering
    vecs_c, mu = apply_centering(vecs)
    cosine_stats(vecs_c, "CENTERED")

    # 3) centering + 상위 PC 제거
    vecs_cp, PCs = apply_remove_top_pcs(vecs_c, k=REMOVE_PC_K)
    cosine_stats(vecs_cp, f"CENTERED+PCREM(k={REMOVE_PC_K})")

    # ---- 특정 두 문장 A,B도 동일 처리해서 cosine 비교 ----
    vA = embedder.embed(text_A)[None, :]
    vB = embedder.embed(text_B)[None, :]

    # raw
    raw_cos = float(np.sum(vA * vB))
    # centered
    vA_c = l2norm_rows(vA - mu)
    vB_c = l2norm_rows(vB - mu)
    cen_cos = float(np.sum(vA_c * vB_c))
    # centered + PC remove
    projA = (vA_c @ PCs.T) @ PCs
    projB = (vB_c @ PCs.T) @ PCs
    vA_cp = l2norm_rows(vA_c - projA)
    vB_cp = l2norm_rows(vB_c - projB)
    pcr_cos = float(np.sum(vA_cp * vB_cp))

    print("\n[PAIR TEST]")
    print(f"  raw cosine                = {raw_cos:.6f}")
    print(f"  centered cosine           = {cen_cos:.6f}")
    print(f"  centered+PC-removed cosine= {pcr_cos:.6f}")

    # ---- calibration 저장(나중에 쿼리에도 동일 적용해야 함) ----
    if SAVE_CALIB:
        out_path = Path("data") / f"korpat_calib_{TEXT_MODE}_pc{REMOVE_PC_K}.pkl"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "wb") as f:
            pickle.dump({"mu": mu.astype(np.float32), "PCs": PCs.astype(np.float32)}, f)
        print(f"\n[Saved] calibration => {out_path}")
