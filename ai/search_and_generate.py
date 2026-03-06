import os
import csv
import json
import argparse
import numpy as np
from pathlib import Path

import torch
from transformers import AutoModel

# 기존 모듈 임포트 유지
from models.KorPatBERT.korpat_tokenizer import Tokenizer
from aimodule.pipeline import GPTPipeline


# ===============================
# PATH CONFIG
# ===============================

DATA_ROOT = "data"
EMBED_DIR = os.path.join(DATA_ROOT, "embeddings_final")
PROCESSED_DIR = os.path.join(DATA_ROOT, "reprocessed")

MODEL_PATH = Path("models/KorPatBERT/pytorch")


# ===============================
# KorPatBERT Embedder
# ===============================

class KorPatBERTEmbedder:
    def __init__(self):
        vocab_file = MODEL_PATH.parent / "pretrained" / "korpat_vocab.txt"

        self.tokenizer = Tokenizer(
            vocab_path=vocab_file,
            cased=True
        )

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        self.model = AutoModel.from_pretrained(MODEL_PATH).to(self.device)
        self.model.eval()

        print(f"[INFO] KorPatBERT loaded on {self.device}")

    def embed(self, text, chunk_size=450):

        # 토큰화 안정화
        tokens = self.tokenizer.tokenize(text)
        tokens = self.tokenizer._convert_tokens_to_ids(tokens)

        if len(tokens) == 0:
            return np.zeros(768)

        chunks = [
            tokens[i:i + chunk_size]
            for i in range(0, len(tokens), chunk_size)
        ]

        vectors = []

        for chunk in chunks:

            chunk = chunk[:512]

            input_ids = torch.LongTensor(chunk).unsqueeze(0).to(self.device)

            attention_mask = torch.ones_like(input_ids).to(self.device)

            with torch.no_grad():

                out = self.model(
                    input_ids=input_ids,
                    attention_mask=attention_mask
                )

            # CLS pooling (더 안정적)
            vec = out.last_hidden_state[:, 0, :].cpu().numpy()[0]

            vectors.append(vec)

        if not vectors:
            return np.zeros(768)

        final_vec = np.mean(vectors, axis=0)

        final_vec /= (np.linalg.norm(final_vec) + 1e-8)

        return final_vec


# ===============================
# LOAD EMBEDDINGS
# ===============================

def load_embeddings():
    files = []
    fields = []
    vectors = []

    embed_path = Path(EMBED_DIR)
    if not embed_path.exists():
        print(f"[ERROR] Embedding directory not found: {EMBED_DIR}")
        return [], [], np.array([])

    for file in embed_path.glob("*_combined_embeddings.csv"):
        field = file.name.replace("_combined_embeddings.csv", "")
        with open(file, encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader) 
            for row in reader:
                files.append(row[0])
                fields.append(field)
                vectors.append(np.array(row[1:], dtype=float))

    if not vectors:
        return [], [], np.array([])

    vectors = np.vstack(vectors)
    vectors /= (np.linalg.norm(vectors, axis=1, keepdims=True) + 1e-8)

    return files, fields, vectors


# ===============================
# LOAD FIELD MEAN
# ===============================

def load_field_means():
    means = {}

    for file in Path(EMBED_DIR).glob("*_combined_mean.npy"):

        field = file.name.replace("_combined_mean.npy", "")

        vec = np.load(file)

        vec = vec / (np.linalg.norm(vec) + 1e-8)

        means[field] = vec

    return means
# ===============================
# FIELD DETECTION
# ===============================

def detect_fields(query_vec, field_means):

    query_vec = query_vec / (np.linalg.norm(query_vec) + 1e-8)

    scores = {}

    for field, mean_vec in field_means.items():

        sim = float(query_vec @ mean_vec)

        scores[field] = sim

    return sorted(scores.items(), key=lambda x: x[1], reverse=True)

# ===============================
# WHITENING
# ===============================

def apply_whitening_to_db(vectors, fields, means):

    new_vectors = []

    for v, f in zip(vectors, fields):

        if f not in means:
            new_vectors.append(v)
            continue

        w = v - means[f]

        w /= (np.linalg.norm(w) + 1e-8)

        new_vectors.append(w)

    return np.vstack(new_vectors)

def apply_whitening_to_query(query_vec, target_field, means):
    w = query_vec - means[target_field]
    w /= (np.linalg.norm(w) + 1e-8)
    return w


# ===============================
# SEARCH
# ===============================

def search(query_vec, files, fields, vectors, topk=10):
    scores = vectors @ query_vec
    idx = np.argsort(scores)[::-1][:topk]

    results = []
    for i in idx:
        results.append({
            "file": files[i],
            "field": fields[i],
            "score": float(scores[i])
        })
    return results


# ===============================
# LOAD PATENT SECTIONS
# ===============================

def load_patent_sections(field, filename):
    base_name = os.path.splitext(filename)[0]
    path = os.path.join(PROCESSED_DIR, field, base_name + ".json")

    if not os.path.exists(path):
        return {}

    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ===============================
# WRITE RESULT
# ===============================

def write_result(user_idea, results, claim_result):
    with open("result.txt", "w", encoding="utf-8") as f:
        f.write("사용자 발명 아이디어\n")
        f.write("=" * 50 + "\n")
        f.write(user_idea + "\n\n")

        f.write("=== 유사 특허 TOP 10 ===\n")
        for i, r in enumerate(results, 1):
            f.write(f"{i:2d}. [{r['field']}] {r['file']} (Score: {r['score']:.4f})\n")

        f.write("\n=== AI 추천 청구항 ===\n")
        if isinstance(claim_result, (dict, list)):
            f.write(json.dumps(claim_result, ensure_ascii=False, indent=2))
        else:
            f.write(str(claim_result))


# ===============================
# MAIN PIPELINE
# ===============================

def run_pipeline(user_idea):
    print("[1/6] Loading embeddings...")
    files, fields, vectors = load_embeddings()
    field_means = load_field_means()
    vectors = apply_whitening_to_db(vectors, fields, field_means)
    if not files:
        print("Data not found. Please check data directory.")
        return

    print("[2/6] Embedding user idea...")
    embedder = KorPatBERTEmbedder()
    query_vec = embedder.embed(user_idea)

    print("[3/6] Predicting field...")
    ranked_fields = detect_fields(query_vec, field_means)
    top_field = ranked_fields[0][0]
    print(f"-> Selected Field: {top_field}")

    print("[4/6] Searching...")
    whitened_query = apply_whitening_to_query(query_vec, top_field, field_means)
    results = search(whitened_query, files, fields, vectors, 10)

    print("[5/6] Generating claim...")
    top1 = results[0]
    
    sections = load_patent_sections(top1["field"], top1["file"])
    
    if not sections:
        print("[WARN] Patent JSON not found. Skipping claim generation.")
        claim = {"error": "patent section missing"}
    else:
        gpt = GPTPipeline()
        claim = gpt.generate_claim(
            elements=sections,
            user_idea=user_idea,
            field=top1["field"]
        )
    
    gpt = GPTPipeline()
    claim = gpt.generate_claim(
        elements=sections,
        user_idea=user_idea,
        field=top1["field"]
    )

    print("[6/6] Saving result...")
    write_result(user_idea, results, claim)
    print("Done. Check 'result.txt'.")


# ===============================
# CLI ENTRY
# ===============================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("idea", type=str)
    args = parser.parse_args()
    run_pipeline(args.idea)


if __name__ == "__main__":
    main()