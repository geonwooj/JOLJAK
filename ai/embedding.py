import os
import re
import json
import random
import csv
import unicodedata
from pathlib import Path
import orjson
import numpy as np
import torch
import glob
from scipy.special import softmax
from tqdm import tqdm
from transformers import AutoModel
# pdf_processor는 기존 환경 유지
try:
    from pdf_processor.pipeline import process_pdf
except ImportError:
    def process_pdf(p, output_dir): return {}
import pickle

# KMP 중복 오류 방지 및 환경 설정
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
DATA_ROOT = "data"
RAW_PDF_DIR = os.path.join(DATA_ROOT, "raw_pdf")
PROCESSED_DIR = os.path.join(DATA_ROOT, "reprocessed")
EMBEDDING_OUT_DIR = os.path.join(DATA_ROOT, "embeddings_temp")
TEST_OUT_DIR = os.path.join(DATA_ROOT, "embeddings_test")

os.makedirs(TEST_OUT_DIR, exist_ok=True)
os.makedirs(EMBEDDING_OUT_DIR, exist_ok=True)

TARGET_FIELDS = ["abstract", "claims", "description"]
SEED = 42
random.seed(SEED)
np.random.seed(SEED)

# ====================== 1. [강화된] 전처리 및 SNR 로직 ======================
def clean_patent_text(text: str) -> str:
    if not text: return ""
    # 유니코드 및 소문자 정규화
    t = unicodedata.normalize("NFKC", text).lower()
    
    # [강화] 특허 상투 문구 및 메타데이터 대폭 제거
    # 이 단어들이 남아있으면 모든 분야의 유사도가 1.0이 됩니다.
    stop_patterns = [
        r"제\s*\d+\s*항", r"도\s*\d+", r"실시예", r"본\s*발명", r"상기", r"전술한", 
        r"상술한", r"특징으로\s*함", r"구성된다", r"포함한다", r"장치", r"방법", 
        r"시스템", r"데이터", r"정보", r"도면", r"위하여", r"의해", r"대한", 
        r"기술분야", r"배경기술", r"해결하고자\s*하는\s*과제", r"발명의\s*효과",
        r"대\s*표\s*도", r"등록특허", r"청구항", r"특허청구의\s*범위", r"\[\d{4}\]"
    ]
    for pattern in stop_patterns:
        t = re.sub(pattern, " ", t)
        
    # 특수문자 및 숫자 제거 (숫자는 모델이 분야를 구분하는 데 방해가 됨)
    t = re.sub(r"[^a-z가-힣\s]", " ", t)
    
    # 너무 짧은 단어 제거 (2글자 미만은 노이즈일 확률이 높음)
    words = [w for w in t.split() if len(w) > 1]
    return " ".join(words)

def calculate_dynamic_weights(scores_dict, eps_j=0.05, tau=1.5):
    """SNR(Signal-to-Noise Ratio) 기반 동적 가중치 계산"""
    results = {}
    s_values = []
    keys = list(scores_dict.keys())

    for field in keys:
        data = scores_dict[field]
        mu_in, mu_out = np.mean(data['in']), np.mean(data['out'])
        sigma_in, sigma_out = np.std(data['in']), np.std(data['out'])

        j = mu_in - mu_out
        sigma_total = np.sqrt(sigma_in**2 + sigma_out**2)
        j_prime = max(j - eps_j, 0)
        s = j_prime / (sigma_total + 1e-6)

        results[field] = {'S': s}
        s_values.append(s)

    weights = softmax(np.array(s_values) / tau)

    for i, field in enumerate(keys):
        results[field]['W'] = weights[i]

    return results

# ====================== 2. [수정] Mean Centering & Save 로직 ======================

def mean_center_and_save(storage, doc_names, field, output_dir):
    """
    Global Centering + Local Centering + Standard Scaling
    단순 평균 제거가 안 통할 때 쓰는 강력한 방법
    """
    for key, embs in storage.items():
        if not embs: continue
        
        X = np.stack(embs, axis=0)

        # 1. Global Centering (특허 문체 자체의 베이스라인 제거)
        # 전체 분야를 아우르는 통합 평균이 있다면 좋겠지만, 
        # 일단 현재 분야(field) 내에서 표준화(Standardization)를 먼저 시도합니다.
        
        mu = X.mean(axis=0, keepdims=True)
        std = X.std(axis=0, keepdims=True) + 1e-8
        
        # Z-Score Normalization (단순 차이만 보는 게 아니라 변동성까지 고려)
        # 유사도가 1.0이라는 건 방향이 같다는 뜻이므로, 분산을 키워 방향을 흩뜨립니다.
        Xc = (X - mu) / std

        # 2. 평균 벡터 저장
        mu_path = os.path.join(output_dir, f"{field}_{key}_mu.npy")
        np.save(mu_path, mu)
        
        # 3. 다시 L2 Normalization (단위구 위로 투영)
        norm = np.linalg.norm(Xc, axis=1, keepdims=True)
        Xc = np.divide(Xc, norm, out=np.zeros_like(Xc), where=norm!=0)

        # 4. 저장
        out_path = os.path.join(output_dir, f"{field}_{key}_embeddings.csv")
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["file"] + [f"d_{i}" for i in range(768)])
            for name, vec in zip(doc_names, Xc):
                writer.writerow([name] + vec.tolist())

# ====================== 3. CUDA 가속 Embedder ======================

class KorPatBERTEmbedder:
    def __init__(self, model_path_base):
        from models.KorPatBERT.korpat_tokenizer import Tokenizer

        # 기존 토크나이저 경로 유지
        self.tokenizer = Tokenizer(
            vocab_path=model_path_base.parent / "pretrained" / "korpat_vocab.txt",
            cased=True
        )

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = AutoModel.from_pretrained(model_path_base).to(self.device)
        self.model.eval()

        print(f"[INFO] Model loaded on {self.device}")

    def embed_document(self, text: str, chunk_size=512, batch_size=16) -> np.ndarray:
        if not text.strip():
            return np.zeros(768, dtype=np.float32)
            
        tokens, _ = self.tokenizer.encode(text, max_len=50000)
        all_chunks = [
            tokens[i:i+chunk_size]
            for i in range(0, len(tokens), chunk_size)
            if len(tokens[i:i+chunk_size]) >= 10
        ]

        if not all_chunks:
            return np.zeros(768, dtype=np.float32)

        embedded_chunks = []

        for i in range(0, len(all_chunks), batch_size):
            batch = all_chunks[i: i + batch_size]
            max_len = max(len(c) for c in batch)
            padded_batch = [c + [0]*(max_len - len(c)) for c in batch]

            input_ids = torch.tensor(padded_batch, dtype=torch.long).to(self.device)
            mask = (input_ids != 0).long().to(self.device)

            with torch.no_grad():
                # 믹스드 프리시전으로 속도 향상
                with torch.amp.autocast(device_type='cuda' if torch.cuda.is_available() else 'cpu'):
                    out = self.model(
                        input_ids=input_ids,
                        attention_mask=mask,
                        output_hidden_states=True
                    )
                    # 마지막 4개 레이어 평균 (BERT 계열에서 성능이 가장 좋음)
                    states = torch.stack(out.hidden_states[-4:]).mean(dim=0)
                    weights = torch.softmax(torch.norm(states, dim=2), dim=1)
                    vecs = torch.sum(states * weights.unsqueeze(-1), dim=1)
                    embedded_chunks.append(vecs.cpu().numpy())

        v = np.mean(np.concatenate(embedded_chunks, axis=0), axis=0)
        # 개별 문서 임베딩 시에도 L2 정규화 적용
        norm_v = np.linalg.norm(v)
        return v / (norm_v + 1e-8) if norm_v > 0 else v


# ====================== 4. 메인 실행 파이프라인 ======================
if __name__ == "__main__":
    # 모델 경로는 사용자 환경에 맞춰 자동 설정
    current_dir = Path(__file__).parent
    base_path = current_dir / "models" / "KorPatBERT" / "pytorch"
    
    if not base_path.exists():
        print(f"❌ 모델 경로를 찾을 수 없습니다: {base_path}")
    else:
        embedder = KorPatBERTEmbedder(base_path)

        # 1. 가중치 계산 (샘플 데이터 - 실제 프로젝트에서는 이 값을 갱신해야 함)
        sample_scores = {
            'abstract': {'in': [0.65, 0.7], 'out': [0.4, 0.45]},
            'claims':    {'in': [0.85, 0.8], 'out': [0.3, 0.35]},
            'description':     {'in': [0.55, 0.6], 'out': [0.45, 0.5]}
        }
        weights_info = calculate_dynamic_weights(sample_scores)

        # 2. 필드별 처리
        if os.path.exists(RAW_PDF_DIR):
            fields = [d for d in os.listdir(RAW_PDF_DIR) if os.path.isdir(os.path.join(RAW_PDF_DIR, d))]

            for field in fields:
                raw_field_dir = os.path.join(RAW_PDF_DIR, field)
                proc_field_dir = os.path.join(PROCESSED_DIR, field)
                os.makedirs(proc_field_dir, exist_ok=True)

                pdf_files = glob.glob(os.path.join(raw_field_dir, "*.pdf"))
                
                storage = {f_name: [] for f_name in TARGET_FIELDS}
                storage["combined"] = []
                doc_names = []

                print(f"\n🚀 {field} 분야 분석 시작 ({len(pdf_files)}개 문서)")

                for pdf_path in tqdm(pdf_files, desc=f"Processing {field}"):
                    pdf_name = os.path.basename(pdf_path)
                    json_path = os.path.join(proc_field_dir, pdf_name.rsplit(".", 1)[0] + ".json")
                    pickle_path = json_path.replace(".json", ".pkl")

                    sections = None
                    # 캐시 로직
                    if os.path.exists(pickle_path):
                        try:
                            with open(pickle_path, "rb") as f:
                                sections = pickle.load(f)
                        except: pass

                    if sections is None:
                        sections = process_pdf(pdf_path, output_dir=proc_field_dir)
                        try:
                            with open(pickle_path, "wb") as f:
                                pickle.dump(sections, f)
                        except: pass

                    # 임베딩 진행
                    current_doc_vecs = {}
                    for f_name in TARGET_FIELDS:
                        text = clean_patent_text(sections.get(f_name, "")) 
                        vec = embedder.embed_document(text)
                        storage[f_name].append(vec)
                        current_doc_vecs[f_name] = vec

                    # Combined 벡터 생성 (SNR 가중치 적용)
                    combined = sum(current_doc_vecs[fn] * weights_info[fn]['W'] for fn in TARGET_FIELDS)
                    norm_c = np.linalg.norm(combined)
                    if norm_c > 0: combined /= norm_c
                    
                    storage["combined"].append(combined)
                    doc_names.append(pdf_name)

                # 5. 후처리 및 저장
                mean_center_and_save(storage, doc_names, field, TEST_OUT_DIR)

            print("\n✅ 임베딩 재추출 완료. 이제 거리 체크 코드를 다시 실행해 보세요!")
        else:
            print(f"❌ RAW_PDF_DIR({RAW_PDF_DIR}) 경로가 존재하지 않습니다.")