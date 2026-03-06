import os
import csv
import json
import argparse
import numpy as np
from pathlib import Path

import torch
from transformers import AutoModel

from models.KorPatBERT.korpat_tokenizer import Tokenizer
from aimodule.pipeline import GPTPipeline


# ===============================
# PATH CONFIG
# ===============================

DATA_ROOT = "data" #데이터 파일의 총 경로

EMBED_CSV_DIR = os.path.join(DATA_ROOT, "embeddings_final") # csv 파일 경로
EMBED_NPY_DIR = os.path.join(DATA_ROOT, "embeddings_final") # npy 파일 경로
PROCESSED_DIR = os.path.join(DATA_ROOT, "reprocessed") # 파싱된 pdf 파일 위치

# 모델 및 보캡 경로
MODEL_PATH = Path("models/KorPatBERT/pytorch") # 모델 경로
VOCAB_PATH = MODEL_PATH.parent / "pretrained" / "korpat_vocab.txt" # vocab 경로


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

    def embed(self, text, chunk_size=450):
        tokens = self.tokenizer.encode(text)
        if len(tokens) > 0 and isinstance(tokens[0], list):
            tokens = tokens[0]

        chunks = [tokens[i:i+chunk_size] for i in range(0, len(tokens), chunk_size)]
        vectors = []

        for chunk in chunks:
            chunk = chunk[:512]
            input_ids = torch.LongTensor(chunk).unsqueeze(0).to(self.device)
            attention_mask = torch.ones_like(input_ids).to(self.device)

            with torch.no_grad():
                out = self.model(input_ids=input_ids, attention_mask=attention_mask)

            vec = out.last_hidden_state.mean(dim=1).cpu().numpy()[0]
            vectors.append(vec)

        if not vectors:
            return np.zeros(768)

        final_vec = np.mean(vectors, axis=0)
        final_vec /= (np.linalg.norm(final_vec) + 1e-8)
        return final_vec


# ===============================
# UTILS & SEARCH
# ===============================

def load_embeddings():
    files, fields, vectors = [], [], []
    embed_path = Path(EMBED_CSV_DIR)
    
    for file in embed_path.glob("*_combined_embeddings.csv"):
        field = file.name.replace("_combined_embeddings.csv", "")
        with open(file, encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader) 
            for row in reader:
                files.append(row[0])
                fields.append(field)
                vectors.append(np.array(row[1:], dtype=float))

    if not vectors: return [], [], np.array([])
    vectors = np.vstack(vectors)
    vectors /= (np.linalg.norm(vectors, axis=1, keepdims=True) + 1e-8)
    return files, fields, vectors

def load_field_means():
    means = {}
    for file in Path(EMBED_NPY_DIR).glob("*_combined_mean.npy"):
        field = file.name.replace("_combined_mean.npy", "")
        means[field] = np.load(file)
    return means

def detect_fields(query_vec, field_means):
    scores = {f: float(query_vec @ (m / (np.linalg.norm(m) + 1e-8))) for f, m in field_means.items()}
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)

def apply_whitening_to_db(vectors, fields, means):
    new_vectors = [ (v - means[f]) / (np.linalg.norm(v - means[f]) + 1e-8) for v, f in zip(vectors, fields)]
    return np.vstack(new_vectors)

def apply_whitening_to_query(query_vec, target_field, means):
    w = query_vec - means[target_field]
    return w / (np.linalg.norm(w) + 1e-8)

def search(query_vec, files, fields, vectors, topk=10):
    scores = vectors @ query_vec
    idx = np.argsort(scores)[::-1][:topk]
    return [{"file": files[i], "field": fields[i], "score": float(scores[i])} for i in idx]

def load_patent_data(field, filename):
    """특허의 JSON 파일에서 섹션(요약 포함) 로드"""
    base_name = os.path.splitext(filename)[0]
    path = os.path.join(PROCESSED_DIR, field, base_name + ".json")
    if not os.path.exists(path): return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ===============================
# WRITE RESULT (가독성 개선)
# ===============================

def write_result(user_idea, results, claim_result):
    with open("result.txt", "w", encoding="utf-8") as f:
        f.write("■ 사용자 발명 아이디어\n")
        f.write("-" * 60 + "\n")
        f.write(user_idea + "\n\n\n")

        f.write("■ 유사 특허 분석 결과 (TOP 10)\n")
        f.write("-" * 60 + "\n")

        for i, r in enumerate(results, 1):
            # 파일명에서 .pdf 제거
            clean_filename = r['file'].replace(".pdf", "").replace(".PDF", "")
            # 점수를 백분율(%)로 변환
            similarity_pct = r['score'] * 100
            
            f.write(f"{i:2d}. [{r['field']}] {clean_filename}\n")
            f.write(f"    ▶ 유사도: {similarity_pct:.2f}%\n")
            
            # 요약 정보 추가 (JSON에 'summary' 또는 'abstract'가 있다고 가정)
            p_data = load_patent_data(r['field'], r['file'])
            summary = p_data.get("summary", p_data.get("abstract", "요약 정보가 없습니다."))
            # 요약이 너무 길 경우 앞부분만 노출
            short_summary = (summary[:120] + "...") if len(summary) > 120 else summary
            f.write(f"    ▶ 요약: {short_summary}\n\n")

        f.write("\n" + "=" * 60 + "\n")
        f.write("■ AI가 추천하는 맞춤형 청구항\n")
        f.write("=" * 60 + "\n\n")

        # 청구항 결과 다듬기
        if isinstance(claim_result, str):
            try:
                claim_result = json.loads(claim_result)
            except:
                pass

        if isinstance(claim_result, dict):
            f.write("[독립항: 제1항]\n")
            f.write(f"{claim_result.get('final_claim_1', '내용 없음')}\n\n")
            
            dep_claims = claim_result.get('final_dependent_claims', [])
            if dep_claims:
                f.write("[종속항]\n")
                for j, d_claim in enumerate(dep_claims, 2):
                    f.write(f"- 제{j}항: {d_claim}\n")
            else:
                f.write("[종속항]\n- 해당 사항 없음\n")
        else:
            f.write(str(claim_result))
            
        f.write("\n\n* 위 청구항은 유사 특허의 구성을 바탕으로 AI가 초안을 작성한 것이며, 법적 효력을 위해서는 변리사의 검토가 필요합니다.")


# ===============================
# MAIN PIPELINE
# ===============================

def run_pipeline(user_idea):
    print("[1/6] 데이터 로드 중...")
    files, fields, vectors = load_embeddings()
    field_means = load_field_means()
    
    if not files:
        print("데이터를 찾을 수 없습니다. 경로 설정을 확인하세요.")
        return

    print("[2/6] 아이디어 임베딩 중...")
    embedder = KorPatBERTEmbedder()
    query_vec = embedder.embed(user_idea)

    print("[3/6] 기술 분야 예측 중...")
    ranked_fields = detect_fields(query_vec, field_means)
    top_field = ranked_fields[0][0]

    print("[4/6] 유사 특허 검색 중...")
    whitened_vectors = apply_whitening_to_db(vectors, fields, field_means)
    whitened_query = apply_whitening_to_query(query_vec, top_field, field_means)
    results = search(whitened_query, files, fields, whitened_vectors, 10)

    print("[5/6] GPT 청구항 생성 중...")
    top1 = results[0]
    sections = load_patent_data(top1["field"], top1["file"])
    
    gpt = GPTPipeline()
    claim = gpt.generate_claim(
        elements=sections,
        user_idea=user_idea,
        field=top1["field"]
    )

    print("[6/6] 결과 저장 중...")
    write_result(user_idea, results, claim)
    print("\n분석 완료! 'result.txt' 파일을 확인하세요.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("idea", type=str)
    args = parser.parse_args()
    run_pipeline(args.idea)

if __name__ == "__main__":
    main()