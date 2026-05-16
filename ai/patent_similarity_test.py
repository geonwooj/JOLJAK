import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
import pickle
import time
import json
import orjson
import glob
import statistics
from pathlib import Path
import numpy as np
from tqdm import tqdm
from pdf_processor.pipeline import process_pdf
from transformers import AutoModel
import torch
import hashlib
from models.KorPatBERT.korpat_tokenizer import Tokenizer

def extract_core_text(sections: dict) -> str:
    return "\n\n".join([
        sections.get("claims", ""),
        sections.get("description", "")[2000:8000]
    ]).strip()


class KorPatBERTEmbedder:
    def __init__(self):
        base = Path(__file__).parent

        # 🔹 KorPat tokenizer (공식)
        self.tokenizer = Tokenizer(
            vocab_path=base / "models" / "KorPatBERT" / "pretrained" / "korpat_vocab.txt",
            cased=True   # 한글이므로 True
        )

        # 🔹 PyTorch KorPatBERT 모델
        self.model_path = base / "models" / "KorPatBERT" / "pytorch"
        self.model = AutoModel.from_pretrained(self.model_path)
        self.model.eval()

        print("[KorPatBERT] tokenizer + model 로드 완료")

    def embed(self, text: str, max_len: int = 512) -> np.ndarray:
        print("A: tokenize start")
        token_ids, _ = self.tokenizer.encode(text, max_len=max_len)

        if not isinstance(token_ids, list):
            token_ids = list(token_ids)

        token_ids = token_ids[:max_len]
        print("B: tokenize done", len(token_ids))

        input_ids = torch.tensor([token_ids], dtype=torch.long)
        attention_mask = (input_ids != 0).long()
        print("C: tensor ready")

        with torch.no_grad():
            print("D: model forward start")
            outputs = self.model(
                input_ids=input_ids,
                attention_mask=attention_mask
            )
            print("E: model forward done")

        last_hidden = outputs.last_hidden_state
        mask = attention_mask.unsqueeze(-1)

        denom = mask.sum(dim=1)
        if torch.any(denom == 0):
            raise ValueError("attention_mask sum == 0")

        emb = (last_hidden * mask).sum(dim=1) / denom
        emb = emb.squeeze(0)

        emb = emb / (torch.norm(emb) + 1e-8)
        print("F: embedding done")

        return emb.cpu().numpy()


def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8)


def main():
    print("="*80)
    print("KorPatBERT 기반 파싱 품질 + 특허 인식 검증 도구 (PyTorch 버전)")
    print("추가: 각 파싱 결과별 pairwise 유사도 포함")
    print("="*80)

    RAW_BASE = "data/raw_pdf"
    PROCESSED_BASE = "data/processed"
    os.makedirs(PROCESSED_BASE, exist_ok=True)

    embedder = KorPatBERTEmbedder()

    field_dirs = [d for d in os.listdir(RAW_BASE) if os.path.isdir(os.path.join(RAW_BASE, d))]
    if not field_dirs:
        print("data/raw_pdf 아래에 분야 폴더가 없습니다.")
        return

    report = {"fields": {}, "global_stats": {}}
    all_embeddings = []        # 모든 PDF 임베딩 저장
    all_pdf_info = []          # PDF 정보 저장

    for field in field_dirs:
        print(f"\n[{field.upper()}] 검증 시작...")
        raw_dir = os.path.join(RAW_BASE, field)
        proc_dir = os.path.join(PROCESSED_BASE, field)
        os.makedirs(proc_dir, exist_ok=True)

        pdf_files = []
        seen = set()
        for ext in ["*.pdf", "*.PDF"]:
            for p in glob.glob(os.path.join(raw_dir, ext)):
                abs_p = os.path.abspath(p)
                if abs_p not in seen:
                    seen.add(abs_p)
                    pdf_files.append(p)
        if not pdf_files:
            print("PDF 파일 없음")
            continue

        field_embeddings = []
        field_pdf_info = []

        for pdf_path in tqdm(pdf_files, desc=f" {field} 처리"):
            pdf_name = os.path.basename(pdf_path)
            json_path = os.path.join(proc_dir, pdf_name.rsplit(".", 1)[0] + ".json")
            pickle_path = json_path.replace(".json", ".pkl")  # 같은 이름에 .pkl 확장자

            sections = None
            load_method = None
            load_time = 0
            if os.path.exists(pickle_path):
                start = time.time()
                try:
                    with open(pickle_path, "rb") as f:
                        sections = pickle.load(f)
                    load_time = time.time() - start
                    load_method = "pickle 캐시"
                except Exception as e:
                    print(f" → pickle 로드 실패 ({e}) → orjson 시도: {pdf_name}")

            # 2. pickle이 없거나 실패하면 orjson으로 JSON 로드
            if sections is None and os.path.exists(json_path):
                start = time.time()
                try:
                    with open(json_path, "rb") as f:
                        sections = orjson.loads(f.read())
                    load_time = time.time() - start
                    load_method = "orjson"

                    # 성공하면 다음부터 사용할 pickle 캐시 생성
                    try:
                        with open(pickle_path, "wb") as f:
                            pickle.dump(sections, f)
                        print(f" → pickle 캐시 생성 완료: {pdf_name}")
                    except Exception as cache_e:
                        print(f" → pickle 저장 실패 ({cache_e}): {pdf_name}")

                except Exception as e:
                    print(f" → orjson 로드 실패 ({e}) → 재파싱: {pdf_name}")

            # 3. 둘 다 실패하거나 파일 없으면 새 파싱
            if sections is None:
                start = time.time()
                print(f" → 새 파싱 시작: {pdf_name}")
                sections = process_pdf(pdf_path, output_dir=proc_dir)
                load_time = time.time() - start
                load_method = "새 파싱"

                # 파싱 후 pickle 캐시 생성 (다음 실행부터 빠르게)
                try:
                    with open(pickle_path, "wb") as f:
                        pickle.dump(sections, f)
                    print(f" → 새 파싱 후 pickle 캐시 생성: {pdf_name}")
                except Exception as cache_e:
                    print(f" → pickle 저장 실패 ({cache_e}): {pdf_name}")

            # 로드 방식과 시간 출력 (디버깅용, 나중에 지워도 됨)
            if load_method:
                print(f" → {load_method} 사용: {pdf_name} ({load_time:.3f}초)")
            else:
                print(f" → 처리 방식 미확인: {pdf_name}")

            # 이후 로직은 그대로
            text = extract_core_text(sections)
            text_hash = hashlib.md5(text.encode("utf-8")).hexdigest()
            print(f" [DEBUG] text hash={text_hash[:10]} len={len(text)}")
            if len(text) < 200:
                print(f" ⚠️ 텍스트 너무 짧음: {pdf_name}")
                continue

            emb = embedder.embed(text)
            norm = np.linalg.norm(emb)
            field_embeddings.append(emb)
            field_pdf_info.append({
                "field": field,
                "pdf": pdf_name,
                "norm": float(norm),
                "text_len": len(text)
            })
            if len(field_embeddings) >= 2:
                diff = np.linalg.norm(field_embeddings[-1] - field_embeddings[0])
                if diff < 1e-6:
                    print(f" 🚨 임베딩 동일 가능성: {pdf_name} (diff={diff:.2e})")
                else:
                    print(f" 🔍 임베딩 차이: {pdf_name} (diff={diff:.4f})")
            # 전체 저장
            all_embeddings.append(emb)
            all_pdf_info.append({
                "field": field,
                "pdf": pdf_name
            })
        # ==================== centroid 계산 ====================
        field_embeddings_np = np.vstack(field_embeddings)  # (N, 768)

        centroid = field_embeddings_np.mean(axis=0)
        centroid = centroid / (np.linalg.norm(centroid) + 1e-8)

        print(f"\n[{field.upper()}] KorPatBERT 일치도 결과")

        field_scores = []

        for emb, info in zip(field_embeddings, field_pdf_info):
            score = float(np.dot(emb, centroid))  # cosine similarity
            info["korpatbert_alignment"] = round(score, 4)
            field_scores.append(score)

            print(f' {info["pdf"]} | alignment = {score:.4f}')

        # ==================== 분야별 보고서 ====================
        report["fields"][field] = {
            "total_pdf": len(pdf_files),
            "valid_parsed": len(field_embeddings),
            "alignment": {
                "avg": round(float(np.mean(field_scores)), 4),
                "std": round(float(np.std(field_scores)), 4),
                "min": round(float(np.min(field_scores)), 4),
                "max": round(float(np.max(field_scores)), 4),
            },
            "samples": field_pdf_info[:5]
        }

    # ==================== 전체 유사도 계산 ====================

    # 보고서 저장
    report_path = "data/parsing_korpatbert_validation.json"

    os.makedirs(os.path.dirname(report_path), exist_ok=True)

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n검증 보고서 저장 완료: {report_path}")
if __name__ == "__main__":
    main()