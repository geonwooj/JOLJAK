import os
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
EMBED_DIR = os.path.join(DATA_ROOT, "embeddings_final_temp")
PROCESSED_DIR = os.path.join(DATA_ROOT, "reprocessed")

MODEL_PATH = Path("models/KorPatBERT/pytorch")
VOCAB_PATH = MODEL_PATH.parent / "pretrained" / "korpat_vocab.txt"

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
        final_vec = (np.mean(all_chunks, axis=0) + np.max(all_chunks, axis=0)) / 2
        final_vec /= (np.linalg.norm(final_vec) + 1e-8)
        return final_vec

# ===============================
# NPZ 전용 UTILS (DB 의존성 제거)
# ===============================

def load_integrated_data():
    """
    [핵심 수정] 모든 {field}_combined_embeddings.npz 파일을 읽어 통합 검색 인덱스를 구축합니다.
    """
    all_files, all_fields, all_vectors = [], [], []
    field_means = {} # npy 파일 없이 npz에서 즉석 계산하기 위함
    
    npz_files = list(Path(EMBED_DIR).glob("*_combined_embeddings.npz"))
    
    if not npz_files:
        print(f"[ERROR] NPZ 파일을 찾을 수 없습니다: {EMBED_DIR}")
        return [], [], np.array([]), {}

    for npz_path in npz_files:
        field = npz_path.name.replace("_combined_embeddings.npz", "")
        
        with np.load(npz_path, allow_pickle=True) as data:
            vectors = data['vectors']      # (N, 768)
            filenames = data['filenames']  # (N,)
            
            all_vectors.append(vectors)
            all_files.extend(filenames.tolist())
            all_fields.extend([field] * len(filenames))
            
            # 실시간 분야별 평균 벡터 계산 (화이트닝 및 분야 예측용)
            field_means[field] = np.mean(vectors, axis=0)
        
    print(f"[INFO] 통합 데이터 로드 완료: 총 {len(all_files)}건 확보")
    return all_files, all_fields, np.vstack(all_vectors), field_means

def detect_fields(query_vec, field_means):
    scores = {f: float(np.dot(query_vec, m / (np.linalg.norm(m) + 1e-8))) for f, m in field_means.items()}
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)

def apply_whitening(vectors, fields, field_means, query_vec, target_field):
    new_db = []
    for v, f in zip(vectors, fields):
        centered = v - field_means.get(f, 0)
        new_db.append(centered / (np.linalg.norm(centered) + 1e-8))
    
    q_centered = query_vec - field_means.get(target_field, 0)
    new_q = q_centered / (np.linalg.norm(q_centered) + 1e-8)
    return np.vstack(new_db), new_q

def search_with_strategy(query_vec, files, fields, vectors, gap_threshold=0.05):
    scores = vectors @ query_vec
    sorted_idx = np.argsort(scores)[::-1]
    sorted_scores = scores[sorted_idx]

    cutoff_idx = 10 
    for i in range(len(sorted_scores) - 1):
        gap = sorted_scores[i] - sorted_scores[i+1]
        if i >= 3 and gap > gap_threshold:
            cutoff_idx = i + 1
            break
    
    cutoff_idx = min(cutoff_idx, 15)
    return [{"file": files[sorted_idx[i]], "field": fields[sorted_idx[i]], "score": float(sorted_scores[i])} for i in range(cutoff_idx)]

def load_patent_data(field, filename):
    clean_name = os.path.splitext(filename)[0]
    path = os.path.join(PROCESSED_DIR, field, clean_name + ".json")
    if not os.path.exists(path): return {}
    with open(path, encoding="utf-8") as f: return json.load(f)

# ===============================
# 리포트 및 파이프라인
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
            f.write(f"    ▶ 요약: {summary[:150]}...\n\n")
        f.write("\n" + "="*60 + "\n■ AI 추천 맞춤형 청구항 (Retrieval-Guided)\n" + "="*60 + "\n\n")
        
        # [수정 포인트] GPT 반환값이 딕셔너리인 경우 처리
        if isinstance(claim_result, dict):
            # 독립항 출력 (final_claim_1 등)
            main_claim = claim_result.get('final_claim_1', "생성된 독립항이 없습니다.")
            f.write(f"[독립항]\n{main_claim}\n\n")
            
            # 종속항 출력 (리스트 형태인 경우)
            dependent_claims = claim_result.get('final_dependent_claims', [])
            if dependent_claims:
                f.write("[종속항]\n")
                for idx, d_claim in enumerate(dependent_claims, 2):
                    f.write(f"제{idx}항. {d_claim}\n")
        else:
            # 딕셔너리가 아닐 경우 기존처럼 문자열로 출력
            f.write(str(claim_result))

        f.write("\n\n" + "-"*60)
        f.write("\n* 본 결과는 선행특허 분석을 바탕으로 생성된 초안입니다.")

def run_pipeline(user_idea):
    print("[1/6] 로컬 NP즈 통합 데이터베이스 구축 중...")
    files, fields, vectors, field_means = load_integrated_data()
    
    if not files:
        print("[FAIL] 로드된 데이터가 없어 중단합니다.")
        return

    embedder = KorPatBERTEmbedder()
    query_vec = embedder.embed(user_idea)

    ranked_fields = detect_fields(query_vec, field_means)
    top_field = ranked_fields[0][0]
    print(f"[INFO] 예측 분야: {top_field}")

    print("[2/6] 정밀 화이트닝 검색 중...")
    w_vectors, w_query = apply_whitening(vectors, fields, field_means, query_vec, top_field)
    results = search_with_strategy(w_query, files, fields, w_vectors, gap_threshold=0.05)

    print("[3/6] 선행기술 Context 추출 중...")
    prior_arts = []
    for r in results[:5]:
        data = load_patent_data(r['field'], r['file'])
        prior_arts.append({"claims": data.get("claims", ""), "abstract": data.get("abstract", "")})

    print("[4/6] GPT 청구항 생성 중...")
    gpt = GPTPipeline()
    claim = gpt.generate_claim(user_idea=user_idea, prior_arts=prior_arts, field=top_field)

    print("[5/6] 분석 리포트 저장 중...")
    write_result(user_idea, results, claim)
    print("\n✅ 로컬 테스트 완료! 'result.txt'가 생성되었습니다.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("idea", type=str)
    args = parser.parse_args()
    run_pipeline(args.idea)