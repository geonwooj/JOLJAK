import os
import sqlite3
import json
import argparse
import unicodedata
import re
import numpy as np
from pathlib import Path

import torch
from transformers import AutoModel

from models.KorPatBERT.korpat_tokenizer import Tokenizer
from aimodule.pipeline import GPTPipeline

# ===============================
# PATH & CONFIG
# ===============================
DATA_ROOT = "data"
DB_PATH = os.path.join(DATA_ROOT, "patent_system.db")
PROCESSED_DIR = os.path.join(DATA_ROOT, "reprocessed")

MODEL_PATH = Path("models/KorPatBERT/pytorch")
VOCAB_PATH = MODEL_PATH.parent / "pretrained" / "korpat_vocab.txt"

# ===============================
# DB 통합 관리 시스템
# ===============================
class PatentDBManager:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.cur = self.conn.cursor()

    def fetch_search_index(self):
        """DB에서 NPZ 경로와 분야 정보를 로드"""
        query = "SELECT id, name, type, resultPath FROM 원본특허DB"
        self.cur.execute(query)
        rows = self.cur.fetchall()
        
        all_ids, all_names, all_types, all_vectors = [], [], [], []
        
        for p_id, p_name, p_type, npz_path in rows:
            if os.path.exists(npz_path):
                with np.load(npz_path, allow_pickle=True) as data:
                    vec = data['vectors']
                    all_vectors.append(vec if vec.ndim > 1 else vec.reshape(1, -1))
                
                # 벡터 개수만큼 메타데이터 복제 (통합 NPZ 대응)
                count = all_vectors[-1].shape[0]
                all_ids.extend([p_id] * count)
                all_names.extend([p_name] * count)
                all_types.extend([p_type] * count)

        return all_ids, all_names, all_types, np.vstack(all_vectors)

    def fetch_repo_meta(self, patent_id):
        """[Pass 3] 외래키를 참조하여 원문 저장소 데이터 획득"""
        query = """
            SELECT b.name, b.pdf, b.type 
            FROM 원본특허DB a 
            JOIN 특허원문저장소 b ON a.patentRepo = b.id 
            WHERE a.id = ?
        """
        self.cur.execute(query, (patent_id,))
        return self.cur.fetchone()

    def log_result(self, idea, field, claim):
        """최종 결과 DB 저장"""
        self.cur.execute('''CREATE TABLE IF NOT EXISTS 생성로그 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            idea TEXT, field TEXT, claim TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        self.cur.execute("INSERT INTO 생성로그 (idea, field, claim) VALUES (?, ?, ?)", (idea, field, claim))
        self.conn.commit()



# ===============================
# KorPatBERT Embedder
# ===============================
class KorPatBERTEmbedder:
    def __init__(self):
        self.tokenizer = Tokenizer(vocab_path=VOCAB_PATH, cased=True)
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = AutoModel.from_pretrained(MODEL_PATH).to(self.device)
        self.model.eval()
        print(f"[INFO] KorPatBERT loaded on {self.device}")

    def clean_query(self, text):
        if not text: return ""
        t = unicodedata.normalize("NFKC", text).lower()
        # [연구 방법론 4-1] 정형 표현 제거
        t = re.sub(r"\b(상기|전술한|본 발명은|특징으로 한다|의한|포함하는|관한 것으로서)\b", " ", t)
        t = re.sub(r"[^0-9a-z가-힣\s\-\_/;]", " ", t)
        t = re.sub(r"\s+", " ", t).strip()
        return t

    def embed(self, text, chunk_size=512):
        text = self.clean_query(text)
        tokens, _ = self.tokenizer.encode(text, max_len=10000)
        if not tokens: return np.zeros(768)

        stride = chunk_size // 2
        chunks = [tokens[i:i+chunk_size] for i in range(0, len(tokens), stride)]
        chunks = chunks[:30] 

        embedded_chunks = []
        for chunk in chunks:
            input_ids = torch.LongTensor(chunk).unsqueeze(0).to(self.device)
            mask = torch.ones_like(input_ids).to(self.device)
            with torch.no_grad():
                out = self.model(input_ids=input_ids, attention_mask=mask, output_hidden_states=True)
                states = torch.stack(out.hidden_states[-4:]).mean(dim=0)
                mask_exp = mask.unsqueeze(-1).expand(states.size()).float()
                sum_embeddings = torch.sum(states * mask_exp, dim=1)
                sum_mask = torch.clamp(mask_exp.sum(dim=1), min=1e-9)
                vec = (sum_embeddings / sum_mask).cpu().numpy()[0]
                embedded_chunks.append(vec)

        all_chunks = np.array(embedded_chunks)
        # [개선] Max-Mean Hybrid Pooling
        final_vec = (np.mean(all_chunks, axis=0) + np.max(all_chunks, axis=0)) / 2
        final_vec /= (np.linalg.norm(final_vec) + 1e-8)
        return final_vec

# ===============================
# UTILS & SEARCH (기존 기능 + 연구 기믹 결합)
# ===============================

def load_dynamic_weights():
    path = os.path.join(EMBED_DIR, "dynamic_weights.json")
    if os.path.exists(path):
        with open(path, "rb") as f: return json.loads(f.read())
    return {"abstract": 0.3, "claims": 0.6, "description": 0.1}
def load_embeddings():
    """
    [NPZ 전용] CSV 로직을 제거하고, 분야별 NPZ 파일에서 벡터와 파일명을 로드합니다.
    - 대상: {field}_combined_embeddings.npz
    - 내부 데이터: 'vectors' (N, 768), 'filenames' (N,)
    """
    files, fields, vectors = [], [], []
    
    # 임베딩 출력 디렉토리에서 *_combined_embeddings.npz 패턴만 탐색
    npz_files = list(Path(EMBED_DIR).glob("*_combined_embeddings.npz"))
    
    if not npz_files:
        print(f"[ERROR] NPZ 임베딩 파일을 찾을 수 없습니다: {EMBED_DIR}")
        return [], [], np.array([])

    for npz_path in npz_files:
        # 파일명에서 분야(field) 추출
        field = npz_path.name.replace("_combined_embeddings.npz", "")
        
        # NPZ 데이터 로드
        with np.load(npz_path, allow_pickle=True) as data:
            v = data['vectors']      # (N, 768) 행렬
            f = data['filenames']    # (N,) 파일명 배열
            
            vectors.append(v)
            files.extend(f.tolist())
            fields.extend([field] * len(f))
        
    print(f"[INFO] NPZ 통합 로드 완료: 총 {len(files)}건의 데이터 확보")
    return files, fields, np.vstack(vectors)

def load_field_means():
    """
    [NPZ 전용] 개별 npy 파일을 로드하는 대신, 
    이미 로드된 각 분야의 벡터들로부터 즉석에서 평균(Mean)을 계산합니다.
    (파일 I/O를 최소화하기 위해 load_embeddings 결과를 활용하는 방식이 효율적입니다)
    """
    # 팁: run_pipeline 내부에서 load_embeddings() 결과를 받아 처리하면 더 빠르지만,
    # 구조 유지를 위해 별도의 npy 파일을 읽는 대신 npz에서 평균을 내는 방식으로 수정합니다.
    means = {}
    npz_files = list(Path(EMBED_DIR).glob("*_combined_embeddings.npz"))

    for npz_path in npz_files:
        field = npz_path.name.replace("_combined_embeddings.npz", "")
        with np.load(npz_path, allow_pickle=True) as data:
            # npz 내부의 vectors 전체 평균을 내어 분야 대표 벡터로 사용
            means[field] = np.mean(data['vectors'], axis=0)
            
    return means

def detect_fields(query_vec, field_means):
    scores = {f: float(np.dot(query_vec, m / (np.linalg.norm(m) + 1e-8))) for f, m in field_means.items()}
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)

def apply_whitening(vectors, fields, field_means, query_vec, target_field):
    """기존 기능: 분야 내 변별력 강화를 위한 중심점 제거"""
    # DB 벡터 화이트닝
    new_db = []
    for v, f in zip(vectors, fields):
        if f in field_means:
            centered = v - field_means[f]
            new_db.append(centered / (np.linalg.norm(centered) + 1e-8))
        else: new_db.append(v)
    
    # 쿼리 화이트닝
    q_centered = query_vec - field_means.get(target_field, 0)
    new_q = q_centered / (np.linalg.norm(q_centered) + 1e-8)
    return np.vstack(new_db), new_q

def search_with_strategy(query_vec, files, fields, vectors, gap_threshold=0.04):
    """[연구 핵심] 인접 유사도 하락폭 기반 Cut-off"""
    scores = vectors @ query_vec
    sorted_idx = np.argsort(scores)[::-1]
    sorted_scores = scores[sorted_idx]

    # Cut-off Rule 적용
    cutoff_idx = 10 
    for i in range(len(sorted_scores) - 1):
        gap = sorted_scores[i] - sorted_scores[i+1]
        if i >= 3 and gap > gap_threshold:
            cutoff_idx = i + 1
            break
    
    cutoff_idx = min(cutoff_idx, 15) # 최대치 제한
    return [{"file": files[sorted_idx[i]], "field": fields[sorted_idx[i]], "score": float(sorted_scores[i])} for i in range(cutoff_idx)]

def load_patent_data(field, filename):
    path = os.path.join(PROCESSED_DIR, field, os.path.splitext(filename)[0] + ".json")
    if not os.path.exists(path): return {}
    with open(path, encoding="utf-8") as f: return json.load(f)

# ===============================
# 리포트 생성 (기존 write_result 유지/보강)
# ===============================

def write_result(user_idea, results, claim_result):
    with open("result.txt", "w", encoding="utf-8") as f:
        f.write("■ 사용자 발명 아이디어\n" + "-"*60 + "\n" + user_idea + "\n\n\n")
        f.write(f"■ 유사 특허 분석 결과 (검색된 선행기술: {len(results)}건)\n" + "-"*60 + "\n")

        for i, r in enumerate(results, 1):
            sim_pct = max(0, min(100, r['score'] * 100))
            f.write(f"{i:2d}. [{r['field']}] {r['file']} (유사도: {sim_pct:.2f}%)\n")
            p_data = load_patent_data(r['field'], r['file'])
            summary = p_data.get("abstract", "요약 정보 없음")
            f.write(f"   ▶ 요약: {summary[:150]}...\n\n")

        f.write("\n" + "="*60 + "\n■ AI 추천 맞춤형 청구항 (Retrieval-Guided)\n" + "="*60 + "\n\n")
        f.write(str(claim_result))
        f.write("\n\n* 본 결과는 선행특허 분석을 바탕으로 생성된 초안입니다.")

# ===============================
# MAIN PIPELINE
# ===============================

def run_pipeline(user_idea):
    db = PatentDBManager(DB_PATH)
    
    print("[1/6] DB 및 NPZ 기반 데이터 로드 중...")
    p_ids, p_names, p_types, vectors = db.fetch_search_index()
    
    # NPY 파일 없이 로드된 벡터에서 즉석 평균 계산
    field_means = {t: np.mean(vectors[[i for i, x in enumerate(p_types) if x == t]], axis=0) for t in set(p_types)}

    embedder = KorPatBERTEmbedder()
    query_vec = embedder.embed(user_idea)

    # 분야 예측 (Cosine Similarity)
    ranked_fields = sorted({t: float(np.dot(query_vec, m / (np.linalg.norm(m) + 1e-8))) for t, m in field_means.items()}.items(), key=lambda x: x[1], reverse=True)
    top_field = ranked_fields[0][0]
    print(f"[INFO] 예측 분야: {top_field}")

    print("[2/6] 화이트닝 및 정밀 검색...")
    w_vectors, w_query = apply_whitening(vectors, p_types, field_means, query_vec, top_field)
    results = search_with_strategy(w_query, p_ids, p_types, w_vectors)

    print("[3/6] 선행기술 Context 추출 (DB JOIN)...")
    prior_arts = []
    for r in results[:5]:
        repo_data = db.fetch_repo_meta(r['id'])
        if repo_data:
            _, pdf_file, r_type = repo_data
            json_path = os.path.join(PROCESSED_DIR, r_type, os.path.splitext(pdf_file)[0] + ".json")
            if os.path.exists(json_path):
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    prior_arts.append({"claims": data.get("claims", ""), "abstract": data.get("abstract", "")})

    print("[4/6] GPT 청구항 생성 중...")
    gpt = GPTPipeline()
    claim = gpt.generate_claim(user_idea=user_idea, prior_arts=prior_arts, field=top_field)

    print("[5/6] 분석 결과 DB 기록 및 리포트 저장...")
    db.log_result(user_idea, top_field, claim)
    print("\n✅ 파이프라인 완료! 결과가 DB에 저장되었습니다.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("idea", type=str)
    args = parser.parse_args()
    run_pipeline(args.idea)