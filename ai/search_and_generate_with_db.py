import os
import sqlite3
import json
import unicodedata
import re
import numpy as np
import torch
from pathlib import Path
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

class PatentDBManager:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.cur = self.conn.cursor()

    def fetch_pending_input(self):
        self.cur.execute("SELECT id, idea_text FROM 사용자입력DB WHERE status = 'pending' ORDER BY created_at ASC LIMIT 1")
        return self.cur.fetchone()

    def load_integrated_search_index(self):
        """DB에서 중복을 제거하며 인덱스 로드"""
        self.cur.execute("SELECT id, name, type, resultPath FROM 원본특허DB")
        rows = self.cur.fetchall()
        
        all_ids, all_files, all_fields, all_vectors = [], [], [], []
        field_vectors_map = {}
        seen_files = set() 

        for p_id, p_name, p_type, npz_path in rows:
            if os.path.exists(npz_path):
                with np.load(npz_path, allow_pickle=True) as data:
                    vecs = data['vectors']
                    f_names = data['filenames'].tolist()
                    
                    for i, fname in enumerate(f_names):
                        if fname not in seen_files:
                            all_vectors.append(vecs[i])
                            all_ids.append(p_id)
                            all_files.append(fname)
                            all_fields.append(p_type)
                            
                            if p_type not in field_vectors_map:
                                field_vectors_map[p_type] = []
                            field_vectors_map[p_type].append(vecs[i])
                            seen_files.add(fname)
        
        field_means = {f: np.mean(np.vstack(v_list), axis=0) for f, v_list in field_vectors_map.items()}
        return all_ids, all_files, all_fields, np.array(all_vectors), field_means

    def update_status(self, i_id, status):
        self.cur.execute("UPDATE 사용자입력DB SET status = ? WHERE id = ?", (status, i_id))
        self.conn.commit()
class KorPatBERTEmbedder:
    def __init__(self):
        self.tokenizer = Tokenizer(vocab_path=VOCAB_PATH, cased=True)
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = AutoModel.from_pretrained(MODEL_PATH).to(self.device)
        self.model.eval()

    def clean_query(self, text):
        if not text: return ""
        t = unicodedata.normalize("NFKC", text).lower()
        t = re.sub(r"\b(상기|전술한|본 발명은|특징으로 한다|의한|포함하는|관한 것으로서)\b", " ", t)
        t = re.sub(r"[^0-9a-z가-힣\s\-\_/;]", " ", t)
        return re.sub(r"\s+", " ", t).strip()

    def embed(self, text):
        text = self.clean_query(text)
        tokens, _ = self.tokenizer.encode(text, max_len=10000)
        if not tokens: return np.zeros(768)

        # 512 길이로 청크 분할 (stride 256)
        chunks = [tokens[i:i+512] for i in range(0, len(tokens), 256)][:30]
        embedded_chunks = []
        
        for chunk in chunks:
            # 1. input_ids 생성
            ids = torch.LongTensor(chunk).unsqueeze(0).to(self.device)
            
            # 2. attention_mask 생성 (0이 아닌 토큰은 1, 패딩인 0은 0으로 표시)
            # KorPatBERT의 패딩 토큰 ID가 0인 경우를 가정합니다.
            mask = (ids != 0).long().to(self.device)
            
            with torch.no_grad():
                # 3. 모델 호출 시 attention_mask 전달 (경고 해결 핵심)
                out = self.model(input_ids=ids, attention_mask=mask, output_hidden_states=True)
                
                # 정확도 전략: 마지막 4개 레이어 평균
                states = torch.stack(out.hidden_states[-4:]).mean(dim=0)
                
                # 마스킹된 부분만 평균 계산 (Padding 제거 효과 강화)
                mask_exp = mask.unsqueeze(-1).expand(states.size()).float()
                sum_embeddings = torch.sum(states * mask_exp, dim=1)
                sum_mask = torch.clamp(mask_exp.sum(dim=1), min=1e-9)
                vec = (sum_embeddings / sum_mask).cpu().numpy()[0]
                
                embedded_chunks.append(vec)

        # Mean + Max Pooling 전략 유지
        final_vec = (np.mean(embedded_chunks, axis=0) + np.max(embedded_chunks, axis=0)) / 2
        return final_vec / (np.linalg.norm(final_vec) + 1e-8)

def search_with_gap_strategy(query_vec, ids, files, fields, vectors, gap_threshold=0.03):
    scores = vectors @ query_vec
    idx = np.argsort(scores)[::-1]
    s_scores = scores[idx]

    cutoff = 10
    for i in range(len(s_scores) - 1):
        if i >= 2 and (s_scores[i] - s_scores[i+1]) > gap_threshold:
            cutoff = i + 1
            break
    cutoff = min(cutoff, 15)
    return [{"id": ids[idx[i]], "file": files[idx[i]], "field": fields[idx[i]], "score": float(s_scores[i])} for i in range(cutoff)]

def write_result(user_idea, results, claim_result):
    """결과 리포트 작성 (요약 정보 포함 및 번호 교정)"""
    with open("result.txt", "w", encoding="utf-8") as f:
        f.write(f"■ 사용자 아이디어:\n{user_idea}\n\n")
        f.write("■ 유사 특허 검색 결과 (중복 제거 및 요약 포함)\n" + "-"*60 + "\n")
        
        for i, r in enumerate(results, 1):
            f.write(f"{i:2d}. [{r['field']}] {r['file']} (유사도: {r['score']*100:.2f}%)\n")
            
            # JSON에서 요약(Abstract) 추출
            json_path = os.path.join(PROCESSED_DIR, r['field'], r['file'].replace(".pdf", ".json"))
            abstract_text = "요약 정보를 찾을 수 없습니다."
            if os.path.exists(json_path):
                try:
                    with open(json_path, "r", encoding="utf-8") as jf:
                        p_data = json.load(jf)
                        abstract_text = p_data.get("abstract", "요약 정보 없음")
                except: pass
            
            f.write(f"    ▶ 요약: {abstract_text[:180]}...\n\n")
        
        f.write("\n" + "="*60 + "\n■ AI 추천 맞춤형 청구항\n" + "="*60 + "\n\n")
        if isinstance(claim_result, dict):
            # 독립항
            f.write(f"[제1항(독립항)]\n{claim_result.get('final_claim_1', '')}\n\n")
            
            # 종속항 보정
            deps = claim_result.get('final_dependent_claims', [])
            for idx, d_claim in enumerate(deps, 2):
                # 인용 번호가 꼬이는 경우 대비 강제 보정
                clean_claim = re.sub(r'^제\s*\d+\s*항에\s*있어서\s*[\,\.]?', '', d_claim).strip()
                f.write(f"제{idx}항. 제1항에 있어서, {clean_claim}\n")
        else:
            f.write(str(claim_result))

def run_pipeline():
    db = PatentDBManager(DB_PATH)
    pending = db.fetch_pending_input()
    if not pending: return

    i_id, user_idea = pending
    try:
        ids, files, fields, vectors, field_means = db.load_integrated_search_index()
        embedder = KorPatBERTEmbedder()
        q_vec = embedder.embed(user_idea)

        # 분야 예측 및 화이트닝 적용
        field_scores = {f: float(np.dot(q_vec, m/(np.linalg.norm(m)+1e-8))) for f, m in field_means.items()}
        top_field = max(field_scores, key=field_scores.get)
        
        centered_vecs = np.array([v - field_means.get(f, 0) for v, f in zip(vectors, fields)])
        w_vecs = centered_vecs / (np.linalg.norm(centered_vecs, axis=1, keepdims=True) + 1e-8)
        
        q_centered = q_vec - field_means.get(top_field, 0)
        w_q = q_centered / (np.linalg.norm(q_centered) + 1e-8)

        results = search_with_gap_strategy(w_q, ids, files, fields, w_vecs)

        # GPT 컨텍스트 추출
        prior_arts = []
        for r in results[:5]:
            p_path = os.path.join(PROCESSED_DIR, r['field'], r['file'].replace(".pdf", ".json"))
            if os.path.exists(p_path):
                with open(p_path, encoding="utf-8") as f:
                    data = json.load(f)
                    prior_arts.append({"claims": data.get("claims", ""), "abstract": data.get("abstract", "")})

        gpt = GPTPipeline()
        claim = gpt.generate_claim(user_idea=user_idea, prior_arts=prior_arts, field=top_field)

        write_result(user_idea, results, claim)
        db.update_status(i_id, 'completed')
        print(f"✅ ID {i_id} 처리 완료: 요약 및 중복 제거 적용됨")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        db.update_status(i_id, 'failed')

if __name__ == "__main__":
    run_pipeline()