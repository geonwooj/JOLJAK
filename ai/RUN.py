import os
import json
import re
import unicodedata
import torch
import numpy as np
from pathlib import Path
import requests
import sys
import fitz  # PyMuPDF - PDF 파싱용 (pip install pymupdf)
import tempfile
from PIL import Image
from transformers import AutoModel
from llava_text import llava_text, build_prompt_input_with_image_caption
from models.KorPatBERT.korpat_tokenizer import Tokenizer

from pdf_processor import pipeline as pdf_pipeline
from pdf_processor import section as pdf_section
from pdf_processor.quality import is_low_quality_text
from pdf_processor.ocr_engine import ocr_pdf_page
from pdf_processor.normalize_dispatch import normalize_page_text
from aimodule.llm_client import LLMClient
from aimodule.parsing.section_text_preprocess import (
    normalize_text_basic,
    phrase_to_pattern,
    remove_phrases,
    _extract_block_from_patterns,
    extract_description_full_minus_background,
    cleanup_artifacts,
    preprocess_section_text,
    _normalize_desc_text
)
from aimodule.parsing.section_centering import l2_normalize_rows, apply_centering


WEB_LINK = "http://localhost:8080/api/signal/"

DATA_ROOT = "data"
PROCESSED_DIR = os.path.join(DATA_ROOT, "reprocessed")
MODEL_PATH = Path("models/KorPatBERT/pytorch")
VOCAB_PATH = MODEL_PATH.parent / "pretrained" / "korpat_vocab.txt"
HF_MODEL_DIR = str(MODEL_PATH) 
NPZ_PATH = Path("data/npz_backup_v1_desc_full_minus_background_centering_dynamic_weight")
NPZ_FINAL_DIR = NPZ_PATH / "final_vectors"
NPZ_SELECTED_DIR = NPZ_PATH / "selected_centered_sections"
JSON_PATH = Path("data/reprocessed")

CHUNK_SIZE = 256  
STRIDE = 256        
MAX_CHUNKS = 8
MAX_TOKEN_LEN = CHUNK_SIZE * MAX_CHUNKS  # = 2048

DESCRIPTION_VIEW = "full_minus_background"
PREPROCESS_VERSION = "v1_desc_full_minus_background_centering_dynamic_weight"
SECTION_STOPWORDS = {
    "abstract": {
        "conservative": [
            "본 발명은",
            "본 발명의 실시예에 따르면",
            "본 발명의 일 실시예에 따르면",
            "일 실시예에 따르면",
            "일 실시예에서",
            "본 실시예에 따르면",
            "에 관한 것이다",
            "를 제공한다",
            "를 포함한다",
            "를 포함하는",
            "의 효과가 있다",
            "할 수 있는 효과가 있다",
        ],
        "strong": [
            "적어도 하나 이상의",
            "하나 이상의",
            "기 설정된",
            "미리 설정된",
            "사용자 단말",
            "복수의",
            "상기",
            "및",
        ],
    },
    "claims": {
        "conservative": [
            "상기",
            "포함하는",
            "포함하고",
            "구비하는",
            "구비하고",
            "방법으로서",
            "장치에 있어서",
            "컴퓨팅 장치에서 수행되는 방법으로서",
            "하나 이상의 프로세서들",
            "하나 이상의 프로그램들",
            "메모리를 구비하고",
        ],
        "strong": [
            "제 1 항에 있어서",
            "제1항에 있어서",
            "제 2 항에 있어서",
            "제2항에 있어서",
            "제 3 항에 있어서",
            "제3항에 있어서",
            "삭제",
            "단계",
            "수단",
            "모듈",
            "복수의",
        ],
    },
    "description": {
        "conservative": [
            "본 발명은",
            "본 발명의 실시예에 따르면",
            "본 발명의 일 실시예에 따르면",
            "일 실시예에 따르면",
            "일 실시예에서",
            "본 실시예에 따르면",
            "예를 들어",
            "예컨대",
            "이하",
            "상기",
            "에 관한 것이다",
        ],
        "strong": [
            "도 1은",
            "도 2는",
            "도 3은",
            "도 4는",
            "도 5는",
            "도 6는",
            "도 7은",
            "도 8은",
            "도 9은",
            "도 10은",
            "도 11은",
            "도 12은",
            "도 13은",
            "도 14은",
            "도 15은",
            "도 16은",
            "도 17은",
            "도면의 간단한 설명",
            "발명을 실시하기 위한 구체적인 내용",
            "기술분야",
            "배경기술",
            "선행기술문헌",
            "발명의 효과",
            "발명의 내용",
            "해결하려는 과제",
            "과제의 해결 수단",
            "복수의",
            "하나 이상의",
        ],
    },
}

DOMAIN_EXTRA_STOPWORDS = {    
    "Ai": {"abstract": {"conservative": [], "strong": []}, "claims": {"conservative": [], "strong": []}, "description": {"conservative": [], "strong": []}},    
    "BigData": {"abstract": {"conservative": [], "strong": []}, "claims": {"conservative": [], "strong": []}, "description": {"conservative": [], "strong": []}},    
    "InfoComm": {"abstract": {"conservative": [], "strong": []}, "claims": {"conservative": [], "strong": []}, "description": {"conservative": [], "strong": []}},    
    "Semiconductor": {"abstract": {"conservative": [], "strong": []}, "claims": {"conservative": [], "strong": []}, "description": {"conservative": [], "strong": []}},
}
FEW_SHOT_PATH = Path("data")
# ─────────────────────────────────────────────────────────────
# PDF 파싱 설정
# ─────────────────────────────────────────────────────────────
PDF_IMAGE_MIN_WIDTH  = 100   # 너무 작은 이미지(로고, 아이콘 등) 무시
PDF_IMAGE_MIN_HEIGHT = 100
PDF_MAX_IMAGES       = 5     # LLaVA에 넘길 최대 이미지 수 (비용/시간 제한)



def parse_pdf_to_prompt_input(pdf_path: str) -> str:
    """
    고도화된 파서를 사용하여 LLM용 통합 프롬프트 생성.
    """
    print(f"\n[PDF] ========== 고도화된 파이프라인 시작 ==========")
    parser = PatentPDFParser()
    parsed = parser.parse(pdf_path)

    sections    = parsed["sections"]
    image_paths = parsed["image_paths"]

    # 1. 섹션 정보를 포함한 구조화된 텍스트 구성
    # LLM이 각 섹션의 역할을 더 잘 이해할 수 있도록 명시적으로 전달합니다.
    structured_text = f"""[PDF 분석 결과]
발명의 명칭: {sections.get('title', 'N/A')}
IPC 분류: {sections.get('ipc', 'N/A')}

【요약】
{sections.get('abstract', '내용 없음')}

【청구범위】
{sections.get('claims', '내용 없음')}

【발명의 설명】
{sections.get('description', '내용 없음')}
"""

    # 2. LLaVA 이미지 캡션 생성 (기존 로직 유지)
    all_captions = []
    if image_paths:
        print(f"[PDF] LLaVA 캡션 생성 중...") 
        for i, img_path in enumerate(image_paths, start=1):
            try:
                caption = llava_text(img_path)
                if caption:
                    all_captions.append(f"[도면 {i} 분석]\n{caption.strip()}")
            except Exception as e:
                print(f"[ERROR] 도면 {i} 캡션 생성 실패: {e}")

    combined_caption = "\n\n".join(all_captions)

    # 3. 최종 Prompt 통합
    if combined_caption:
        prompt_input = build_prompt_input_with_image_caption(
            raw_input=structured_text,
            image_caption=combined_caption,
        )
    else:
        prompt_input = structured_text

    print(f"[PDF] ========== 파이프라인 완료 (최종 길이: {len(prompt_input)}) ==========\n")
    return prompt_input
    
class PatentPDFParser:
    """
    사용자의 pdf_processor를 활용하여 OCR, 섹션화, 정규화를 수행하는 파서.
    """

    def __init__(self,
                 min_width: int  = PDF_IMAGE_MIN_WIDTH,
                 min_height: int = PDF_IMAGE_MIN_HEIGHT,
                 max_images: int = PDF_MAX_IMAGES):
        self.min_width  = min_width
        self.min_height = min_height
        self.max_images = max_images

    def extract_text(self, pdf_path: str) -> str:
        """
        PDF에서 텍스트를 추출하고 필요시 OCR 및 정규화 수행.
        추출된 텍스트가 min_chars보다 짧은 페이지는 최종 결과에서 제외함.
        """
        print(f"[DEBUG] PatentPDFParser.extract_text (Enhanced): {pdf_path}")
        doc = fitz.open(pdf_path)
        full_text_list = []
        min_chars = 200
        for page_num, page in enumerate(doc, start=1):
            # 1. 기본 텍스트 추출
            text = page.get_text("text").strip()
            
            # 2. 품질 체크 및 OCR (pdf_processor 로직)
            if is_low_quality_text(text):
                print(f"[DEBUG] 페이지 {page_num}: 저품질 텍스트 감지, OCR 실행...")
                text = ocr_pdf_page(page)
            
            # 3. 페이지 단위 정규화 (pdf_processor 로직)
            text = normalize_page_text(text)
            
            # 4. 짧은 텍스트 페이지 제거 로직 추가
            if text and len(text.strip()) >= min_chars:
                full_text_list.append(f"[페이지 {page_num}]\n{text}")
            else:
                reason = "텍스트 없음" if not text else f"길이 부족({len(text.strip())}자)"
                print(f"[DEBUG] 페이지 {page_num}: {reason}으로 인해 제외되었습니다.")

        doc.close()
        return "\n\n".join(full_text_list)

    def extract_images(self, pdf_path: str, output_dir: str = None) -> list:
        """사용자의 pipeline.py 내 이미지 추출 로직 활용"""
        print(f"[DEBUG] PatentPDFParser.extract_images (Enhanced): {pdf_path}")
        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="patent_pdf_images_")
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        pdf_id = Path(pdf_path).stem
        doc = fitz.open(pdf_path)
        
        # 사용자 pipeline의 이미지 추출 함수 호출
        # (summary에 따르면 pdf_id, doc, output_dir을 인자로 받음)
        image_info_list = pdf_pipeline.extract_and_save_images(doc, pdf_id, output_dir)
        doc.close()

        saved_paths = []
        for img_info in image_info_list:
            if len(saved_paths) >= self.max_images or len(saved_paths) >= 5:
                break
            # 이미지 정보 딕셔너리에서 경로 추출
            if "path" in img_info:
                saved_paths.append(img_info["path"])
            
        print(f"[DEBUG] 총 {len(saved_paths)}개 이미지 추출 완료")
        return saved_paths

    def parse(self, pdf_path: str) -> dict:
        """통합 파싱 (텍스트 + 이미지 + 섹션 구조화)"""
        print(f"[DEBUG] PatentPDFParser.parse: 시작")
        
        # 1. 텍스트 추출 (OCR 포함)
        raw_text = self.extract_text(pdf_path)
        
        # 2. 이미지 추출
        image_paths = self.extract_images(pdf_path)
        
        # 3. 섹션 추출 (pdf_processor.section 로직)
        print(f"[DEBUG] 섹션 분리 중...")
        sections = pdf_section.extract_sections(raw_text)

        doc = fitz.open(pdf_path)
        page_count = doc.page_count
        doc.close()

        return {
            "raw_text": raw_text,
            "sections": sections,
            "image_paths": image_paths,
            "page_count": page_count,
        }
def detect_input_type(user_input: str) -> str:
    """
    사용자 입력이 PDF 파일 경로인지, 일반 텍스트인지 판별.

    Returns:
        "pdf"  - .pdf 확장자 파일이 실제로 존재하는 경우
        "text" - 그 외 모든 경우
    """
    stripped = user_input.strip()
    if stripped.lower().endswith(".pdf") and Path(stripped).exists():
        return "pdf"
    return "text"

def load_npz_pack(path: Path):
    print(f"[DEBUG] load_npz_pack: 파일 로드 시작 - {path}")
    print(f"[DEBUG] load_npz_pack: 파일 존재 여부 - {path.exists()}")
    
    if not path.exists():
        print(f"[DEBUG] load_npz_pack: ❌ 파일 없음 - {path}")
        raise FileNotFoundError(f"NPZ file not found: {path}")
    
    try:
        with np.load(path, allow_pickle=True) as z:
            print(f"[DEBUG] load_npz_pack: NPZ 열기 성공")
            print(f"[DEBUG] load_npz_pack: 포함된 키 - {list(z.keys())}")
            
            vectors = z["vectors"].astype(np.float32)
            print(f"[DEBUG] load_npz_pack: vectors shape - {vectors.shape}, dtype - {vectors.dtype}")
            
            labels = z["labels"].astype(str).tolist()
            print(f"[DEBUG] load_npz_pack: labels 길이 - {len(labels)}, 샘플 - {labels[:3] if labels else 'empty'}")
            
            doc_ids = z["doc_ids"].astype(str).tolist()
            print(f"[DEBUG] load_npz_pack: doc_ids 길이 - {len(doc_ids)}, 샘플 - {doc_ids[:3] if doc_ids else 'empty'}")

            meta = {}
            if "meta" in z:
                try:
                    meta = json.loads(str(z["meta"].item()))
                    print(f"[DEBUG] load_npz_pack: meta 파싱 성공 - {len(meta)} keys")
                except Exception as e:
                    print(f"[DEBUG] load_npz_pack: ⚠️ meta 파싱 실패 - {e}")
                    meta = {}

        return {
            "vectors": vectors,
            "labels": labels,
            "doc_ids": doc_ids,
            "meta": meta,
        }
    except Exception as e:
        print(f"[DEBUG] load_npz_pack: ❌ 예외 발생 - {type(e).__name__}: {e}")
        raise


# --- 1. KorPatBERT 임베딩 엔진 ---
class KorPatBERTEmbedder:

    def __init__(self):
        self.device      = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.max_seq_len = CHUNK_SIZE
        print(f"[DEBUG] KorPatBERTEmbedder: device={self.device}")

        if not VOCAB_PATH.exists():
            raise FileNotFoundError(f"Vocab file not found: {VOCAB_PATH}")

        self.tokenizer = Tokenizer(vocab_path=str(VOCAB_PATH), cased=True)
        self.model = AutoModel.from_pretrained(HF_MODEL_DIR, local_files_only=True).to(self.device)
        self.model.eval()
        self.hidden_size = self.model.config.hidden_size
        print(f"[DEBUG] KorPatBERTEmbedder: hidden_size={self.hidden_size}")

    def embed_text(self, text: str) -> np.ndarray:
        if not text:
            return np.zeros(self.hidden_size, dtype=np.float32)

        try:
            token_ids, _ = self.tokenizer.encode(text, max_len=None)
        except Exception as e:
            print(f"[DEBUG] embed_text: 토큰화 실패 - {e}")
            return np.zeros(self.hidden_size, dtype=np.float32)

        if not token_ids:
            return np.zeros(self.hidden_size, dtype=np.float32)

        actual_tokens = token_ids[1:-1]
        max_chunk_len = self.max_seq_len - 2
        chunks = [actual_tokens[i:i + max_chunk_len]
                  for i in range(0, len(actual_tokens), STRIDE)]
        chunks = chunks[:MAX_CHUNKS]

        embedded_chunks = []
        with torch.no_grad():
            for chunk in chunks:
                cls_id = self.tokenizer._token_dict[self.tokenizer._token_cls]
                sep_id = self.tokenizer._token_dict[self.tokenizer._token_sep]
                chunk_ids     = [cls_id] + chunk + [sep_id]
                attention_mask = [1] * len(chunk_ids)
                pad_len = self.max_seq_len - len(chunk_ids)
                if pad_len > 0:
                    chunk_ids.extend([self.tokenizer._pad_index] * pad_len)
                    attention_mask.extend([0] * pad_len)

                outputs = self.model(
                    input_ids      = torch.tensor([chunk_ids]).to(self.device),
                    attention_mask = torch.tensor([attention_mask]).to(self.device)
                )
                seq_out = outputs.last_hidden_state[0].detach().cpu().numpy()
                mask_np = np.array(attention_mask, dtype=np.float32)[:, None]
                denom   = np.clip(mask_np.sum(), 1.0, None)
                embedded_chunks.append((seq_out * mask_np).sum(axis=0) / denom)

        if not embedded_chunks:
            return np.zeros(self.hidden_size, dtype=np.float32)

        final_vec = np.mean(np.asarray(embedded_chunks, dtype=np.float32), axis=0)
        final_vec = final_vec / (np.linalg.norm(final_vec) + 1e-8)
        return final_vec.astype(np.float32)


# --- 2. Pre-computed .npz 기반 검색 엔진 ---

class PreComputedPatentSearcher:
    def __init__(self, embedder, root_path, metadata_root):
        self.embedder       = embedder
        self.root_path      = Path(root_path)
        self.metadata_root  = Path(metadata_root)
        self.current_domain = None
    def _load_domain_assets(self, domain):
        if domain == self.current_domain:
            return

        final_path = (
            self.root_path / "final_vectors" /
            f"final_dynamic_by_domain__center-section__source-x__{PREPROCESS_VERSION}.npz"
        )

        if not final_path.exists():
            raise FileNotFoundError(f"Final NPZ not found: {final_path}")

        final_data   = load_npz_pack(final_path)
        self.vectors = final_data["vectors"].astype("float32")
        self.doc_ids = final_data["doc_ids"]
        self.labels  = np.array(final_data["labels"])

        meta_data   = final_data["meta"]
        weights_map = meta_data.get("weights_by_domain", {}).get(domain, {})
        modes_map   = meta_data.get("best_modes", {})

        assets = {}
        for section in ["abstract", "claims", "description"]:
            mode   = modes_map.get(section, "x")
            weight = weights_map.get(section, 1 / 3)

            sec_filename = (
                f"{domain}__{section}__best-{mode}__center-section"
                f"__{PREPROCESS_VERSION}.npz"
            )
            sec_path = self.root_path / "selected_centered_sections" / sec_filename
            center_vec = None

            if sec_path.exists():
                try:
                    sec_data   = load_npz_pack(sec_path)
                    center_vec = np.mean(sec_data["vectors"], axis=0)
                except Exception as e:
                    print(f"[DEBUG] _load_domain_assets: {section} center 로드 실패 - {e}")

            assets[section] = {"center": center_vec, "W": weight}

        self.domain_assets  = assets
        self.current_domain = domain

    def search(self, sectioned_input, k=10):
        domain = sectioned_input.get("type", "Ai")
        self._load_domain_assets(domain)

        v_abs = self.embedder.embed_text(sectioned_input["abstract"]["clean"])
        v_clm = self.embedder.embed_text(sectioned_input["claims"]["clean"])
        v_dsc = self.embedder.embed_text(sectioned_input["description"]["clean"])

        w_abs = self.domain_assets["abstract"]["W"]
        w_clm = self.domain_assets["claims"]["W"]
        w_dsc = self.domain_assets["description"]["W"]

        combined    = (v_abs * w_abs) + (v_clm * w_clm) + (v_dsc * w_dsc)
        final_query = l2_normalize_rows(combined.reshape(1, -1))

        mask           = (self.labels == domain)
        actual_indices = np.where(mask)[0]

        if len(actual_indices) == 0:
            return []

        target_vectors = self.vectors[actual_indices]
        scores         = np.dot(target_vectors, final_query.T).flatten()
        rel_indices    = np.argsort(scores)[::-1][:k]

        results = []
        for r_idx in rel_indices:
            orig_idx = actual_indices[r_idx]
            results.append({
                "doc_id": self.doc_ids[orig_idx],
                "score":  float(scores[r_idx]),
                "text":   self._load_original_text(self.doc_ids[orig_idx], domain),
                "domain": domain,
            })

        return results

    def _load_original_text(self, doc_id, domain):
        target_file = self.metadata_root / domain / f"{doc_id}.json"
        if target_file.exists():
            try:
                with open(target_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}



# --- 3. 최종 파이프라인 (Prompting & Orchestration) ---
class PatentGenerationPipeline:
    def __init__(self, searcher, llm_client):
        self.searcher = searcher
        self.llm = llm_client

    def split_input_sections(self, raw_input, few_shots):
        
        system = """너는 한국어 특허 문서 구조화 및 임베딩 전처리 보조 LLM이다."""
        
           
        prompt = f"""
        
사용자가 입력한 발명 아이디어 또는 기술 설명을 분석하여, 특허 검색용 JSON으로 변환하라.
출력은 반드시 valid JSON 형식만 사용하고, JSON 바깥에 설명을 쓰지 마라.

작성 시, 제공된 예시 형태를 보고 'JSON으로 변환된 특허'의 양식에 맞춰 작성하라.
제공된 예시는 오로지 형태를 잡기 위한 수단으로만 사용되며, 절대로 내용을 참고하지 마라.

[예시 JSON 파일 형태]
{few_shots}
너의 목표는 단순한 특허 문장 생성이 아니라, KorPatBERT 임베딩 검색에 적합한 section별 의미 텍스트를 만드는 것이다.

[전체 처리 순서]

1. 사용자의 입력을 분석하여 기술 분야 type을 분류한다.
   type은 반드시 다음 중 하나여야 한다.
   - Ai
   - BigData
   - InfoComm
   - Semiconductor

2. 입력 내용을 다음 세 section으로 나눈다.
   - abstract
   - claims
   - description

3. 각 section에 대해 raw와 clean을 모두 생성한다.
   - raw: 특허 문서 스타일에 가까운 원문형 서술
   - clean: 임베딩 검색을 위해 공통항과 형식적 표현을 제거한 의미 중심 서술

4. clean 생성 시 아래 정규화 규칙과 공통항 제거 규칙을 반드시 적용한다.

[정규화 규칙]

다음 규칙은 normalize_text_basic, cleanup_artifacts, remove_phrases 함수를 언어 규칙으로 변환한 것이다.

- 불필요한 반복 공백을 하나의 공백으로 줄인다.
- 줄바꿈이 많을 경우 의미 단위만 유지하고 과도한 줄바꿈은 제거한다.
- 특허 번호, 등록번호, 문헌번호처럼 검색 의미와 직접 관련 없는 식별자는 제거한다.
- "[0001]", "[0010]" 같은 문단 번호는 제거한다.
- "- 1 -", "- 2 -" 같은 페이지 표식은 제거한다.
- claims section에서는 "청구항 1", "청구항 2", "제1항에 있어서" 같은 형식적 항 번호 표현을 제거한다.
- 단, 핵심 구성요소, 처리 단계, 기술 효과, 데이터 흐름, 장치 구성은 삭제하지 않는다.
- 의미가 불명확한 내용을 임의로 보충하지 않는다.
- 사용자가 제공하지 않은 수치, 장치명, 알고리즘명, 효과를 새로 만들어내지 않는다.

[description 처리 규칙]

description은 전체 설명을 그대로 요약하지 말고, background를 제외한 본문 중심 section으로 재구성한다.

제외하거나 약화할 내용:
- 기술분야
- 배경기술
- 선행기술문헌
- 일반적인 문제 제기
- 시장 상황
- 기존 기술의 장황한 설명

남겨야 할 내용:
- 발명의 구성요소
- 실제 동작 방식
- 처리 흐름
- 데이터 입력과 출력
- 모듈 간 관계
- 시스템 구조
- 구현 방법
- 실시예의 핵심 동작
- 기존 기술과 구별되는 기술적 차이

[이미지 기반 도면 설명 처리 규칙]

사용자 입력에 [이미지 기반 도면 설명]이 포함된 경우, 이는 사용자가 첨부한 이미지를 LLaVA Caption으로 변환한 보조 설명이다.

- 이미지 기반 도면 설명은 주로 description.raw와 description.clean 생성에 반영한다.
- 이미지 기반 도면 설명에 포함된 구성요소, 연결관계, 처리 흐름, 장치 배치, 모듈 관계는 description에 남긴다.
- 단, "이미지 d에 대한 설명", "도면은", "그림은", "보여준다" 같은 도면 설명용 표현은 clean에서 제거하거나 약화한다.
- 이미지 caption만으로 확정할 수 없는 기능, 효과, 알고리즘명, 수치, 장치명은 임의로 보충하지 않는다.
- 사용자 텍스트 입력과 이미지 기반 도면 설명이 충돌할 경우, 사용자 텍스트 입력을 우선하고 충돌 가능성을 missing_information에 기록한다.
- 이미지 기반 도면 설명이 단순한 시각 묘사에 그치는 경우, 이를 청구항의 권리범위로 과도하게 확장하지 않는다.

[section별 공통항 제거 규칙]

abstract clean에서는 다음 표현을 제거하거나 약화한다.
- 본 발명은
- 본 발명의 실시예에 따르면
- 본 발명의 일 실시예에 따르면
- 일 실시예에 따르면
- 일 실시예에서
- 본 실시예에 따르면
- 에 관한 것이다
- 를 제공한다
- 를 포함한다
- 를 포함하는
- 의 효과가 있다
- 할 수 있는 효과가 있다
- 적어도 하나 이상의
- 하나 이상의
- 기 설정된
- 미리 설정된
- 사용자 단말
- 복수의
- 상기
- 및

claims clean에서는 다음 표현을 제거하거나 약화한다.
- 상기
- 포함하는
- 포함하고
- 구비하는
- 구비하고
- 방법으로서
- 장치에 있어서
- 컴퓨팅 장치에서 수행되는 방법으로서
- 하나 이상의 프로세서들
- 하나 이상의 프로그램들
- 메모리를 구비하고
- 제 1 항에 있어서
- 제1항에 있어서
- 제 2 항에 있어서
- 제2항에 있어서
- 제 3 항에 있어서
- 제3항에 있어서
- 삭제
- 단계
- 수단
- 모듈
- 복수의

단, claims clean에서는 형식어를 제거하더라도 권리범위의 핵심이 되는 구성요소와 처리 순서는 반드시 유지한다.

description clean에서는 다음 표현을 제거하거나 약화한다.
- 본 발명은
- 본 발명의 실시예에 따르면
- 본 발명의 일 실시예에 따르면
- 일 실시예에 따르면
- 일 실시예에서
- 본 실시예에 따르면
- 예를 들어
- 예컨대
- 이하
- 상기
- 에 관한 것이다
- 도 1은
- 도 2는
- 도 3은
- 도 4는
- 도 5는
- 도 6는
- 도 7은
- 도 8은
- 도 9은
- 도 10은
- 도 11은
- 도 12은
- 도 13은
- 도 14은
- 도 15은
- 도 16은
- 도 17은
- 도면의 간단한 설명
- 발명을 실시하기 위한 구체적인 내용
- 기술분야
- 배경기술
- 선행기술문헌
- 발명의 효과
- 발명의 내용
- 해결하려는 과제
- 과제의 해결 수단
- 복수의
- 하나 이상의

[section 작성 규칙]

abstract.raw:
- 특허 초록처럼 발명의 목적, 핵심 구성, 주요 동작을 짧게 요약한다.

abstract.clean:
- 형식적 특허 표현을 제거하고, 기술 핵심어와 작동 원리 중심으로 작성한다.
- 너무 짧게 만들지 말고, 검색 임베딩에 필요한 의미 단서를 충분히 남긴다.

claims.raw:
- 청구항 스타일로 작성한다.
- 독립항에 가까운 구조로 핵심 구성요소와 처리 단계를 포함한다.

claims.clean:
- 청구항 번호, 상기, 포함하는 등의 형식어를 제거한다.
- 대신 핵심 권리범위가 되는 구성요소, 입력, 처리, 출력, 판단 조건은 유지한다.
- 단순 문장 요약이 아니라 검색 가능한 기술 구성 중심 문장으로 만든다.

description.raw:
- 상세설명 스타일로 발명의 구조와 작동 방식을 설명한다.

description.clean:
- background를 제외한다.
- 발명의 실제 동작, 데이터 흐름, 시스템 구성, 알고리즘 처리 과정 중심으로 작성한다.
- 도면 설명식 문장은 제거하되, 도면이 의미하는 구성 관계는 문장에 남긴다.

[출력 JSON schema]

{{
  "type": "Ai | BigData | InfoComm | Semiconductor",
  "type_reason": "해당 type으로 분류한 이유",
  "abstract": {{
    "raw": "특허 초록 스타일 원문형 서술",
    "clean": "정규화 및 공통항 제거 후 임베딩용 abstract"
  }},
  "claims": {{
    "raw": "청구항 스타일 원문형 서술",
    "clean": "정규화 및 공통항 제거 후 임베딩용 claims"
  }},
  "description": {{
    "raw": "상세설명 스타일 원문형 서술",
    "clean": "background 제외 후 구현/동작 중심 임베딩용 description"
  }},
  "normalization_log": {{
    "abstract_removed_or_weakened": ["제거하거나 약화한 abstract 공통 표현"],
    "claims_removed_or_weakened": ["제거하거나 약화한 claims 공통 표현"],
    "description_removed_or_weakened": ["제거하거나 약화한 description 공통 표현"]
  }},
  "missing_information": [
    "사용자 입력만으로 확정할 수 없는 정보"
  ]
}}

[중요 제한]

- 반드시 JSON만 출력한다.
- 설명 문장, 마크다운, 코드블록을 출력하지 않는다.
- 사용자가 제공하지 않은 구체적 구현 세부사항은 임의로 만들지 않는다.
- clean은 raw보다 짧아질 수 있지만, 기술 의미가 사라질 정도로 과도하게 축약하지 않는다.
- 검색 임베딩에 필요한 핵심 명사, 동사, 기술 관계는 유지한다.
사용자 입력:
<<<
{raw_input}
>>>        
        """

        try:
            response  = self.llm.call(system, prompt)
            match     = re.search(r'\{.*\}', response, re.S)
            if not match:
                raise ValueError("No JSON found in response")
            res_json  = json.loads(match.group())

            for field in ["type", "abstract", "claims", "description"]:
                if field not in res_json:
                    raise ValueError(f"Missing field: {field}")

            return res_json

        except json.JSONDecodeError as e:
            print(f"[DEBUG] split_input_sections: JSON 파싱 실패 - {e}")
            return self._get_default_response(raw_input)
        except Exception as e:
            print(f"[DEBUG] split_input_sections: 실패 - {e}")
            return self._get_default_response(raw_input)
    def _get_default_response(self, raw_input):
        return {
            "type": "Ai", "type_reason": "기본값",
            "abstract":    {"raw": raw_input, "clean": raw_input},
            "claims":      {"raw": raw_input, "clean": raw_input},
            "description": {"raw": raw_input, "clean": raw_input},
            "normalization_log": {
                "abstract_removed_or_weakened":    [],
                "claims_removed_or_weakened":      [],
                "description_removed_or_weakened": []
            },
            "missing_information": ["LLM 처리 실패로 인한 기본값"]
        }
       
       
    def run(self, user_input, num_fewshots=5):
        """
        ✅ user_input은 텍스트 또는 이미 parse_pdf_to_prompt_input()로
           변환된 통합 문자열 모두 허용.
        """
        print(f"[DEBUG] run: 사용자 입력 길이 - {len(user_input)}")
        fewshot_path = FEW_SHOT_PATH / "few-shot.json"
        if not fewshot_path.exists():
            return "ERROR: Few-shot 경로 탐색 실패"

        try:
            with open(fewshot_path, "r", encoding="utf-8") as f:
                fs_data = json.load(f)
            input_few_shots = [fs_data]
        except Exception as e:
            print(f"[DEBUG] run: Few-shot 로드 실패 - {e}")
            return "ERROR: Few-shot 데이터 로드 실패"

        print("[DEBUG] run: 1. 섹션화 및 정규화 중...")
        requests.post(WEB_LINK + "10001")
        sectioned_input = self.split_input_sections(user_input, input_few_shots)

        print(f"[DEBUG] run: 2. 유사 특허 검색 중 (도메인: {sectioned_input.get('type')})...")
     
        requests.post(WEB_LINK + "10002")
        try:
            raw_results = self.searcher.search(sectioned_input, k=10)
        except Exception as e:
            return f"ERROR: 특허 검색 실패 - {e}"

        few_shots         = []
        MIN_SCORE_THRESHOLD = 0.05

        for res in raw_results:
            if res["score"] < MIN_SCORE_THRESHOLD and len(few_shots) >= 2:
                continue
            few_shots.append(res)
            if len(few_shots) >= num_fewshots:
                break

        print(f"[DEBUG] run: {len(few_shots)}개 참조 사례 확보.")
        print("[DEBUG] run: 3. 최종 명세서 생성 중...")
        requests.post(WEB_LINK + "10003")
        
        final_prompt = self._build_final_prompt(sectioned_input, few_shots)
        result       = self.llm.call("당신은 대한민국 최고 수준의 특허 변리사입니다.", final_prompt)
        return result
    def _build_final_prompt(self, input_json, few_shots):
        examples_str = ""
        for i, fs in enumerate(few_shots):
            text_obj     = fs.get("text", {})
            abstract     = text_obj.get("abstract", "내용 없음") if text_obj else "내용 없음"
            claims       = text_obj.get("claims",   "내용 없음") if text_obj else "내용 없음"
            abstract_snip = abstract[:600] + ("..." if len(abstract) > 600 else "")
            examples_str += f"""
### [참고 유사 사례 {i+1}]
- 문서번호: {fs['doc_id']}
- 유사도 점수: {fs['score']:.4f}
- 발명의 요약: {abstract_snip}
- 핵심 청구범위: {claims}
"""
        print("[DEBUG] _build_final_prompt: ✅ 프롬프트 생성 완료")
        return f"""
귀하는 아래의 '작성할 발명의 구성'을 바탕으로 정식 특허 명세서를 작성해야 합니다.
작성 시, 위에 제공된 {len(few_shots)}건의 '참고 유사 사례'들의 전문 용어, 문장 구조, 기술적 권리 범위 확장 방식을 적극적으로 참고하십시오.

[참고할 유사 특허 예시들]
{examples_str}

[작성할 발명의 구성 (사용자 입력)]
- 기술 분야: {input_json.get('type', '미분류')}
- 발명의 요약: {input_json['abstract']['raw']}
- 핵심 구성(Raw): {input_json['claims']['raw']}
- 상세 설명 기초: {input_json['description']['raw']}

[작성 지침]
1. 제공된 모든 참고 사례의 서술 양식(상기, 특징으로 하는 등)을 혼합하여 전문적인 문체를 유지하십시오.
2. 각 사례의 차별점을 분석하여, 사용자 아이디어가 가진 고유의 기술적 구성을 더욱 구체화하십시오.
3. 출력은 반드시 [사용자의 아이디어 요약], [유사 특허 목록], [발명의 명칭], [특허청구범위], [발명의 설명] 순서로 섹션을 포함해야 합니다.
4. 설명 문장, 마크다운, 코드블록을 출력하지 않는다.
5. 유사 특허 예시를 작성할때, 도메인의 이름은 출력하지 않고 오로지 특허 요약만을 제시한다.
6. 명확한 구분을위해 '-' 문자를 여러개 사용하여 행을 구분하라.
7. 사용자 입력에 도면에 대한 묘사가 없는 경우 도면의 묘사는 포함하지 않는다.
8. 명세서 작성이 끝난 후, '원하시면 ~해 드릴 수 있습니다'와 같은 추가 제안이나 후속 작업을 묻는 문장을 절대 포함하지 마십시오. 답변은 명세서 본문으로만 끝맺음하십시오.
"""
# --- 실행 예시 ---
if __name__ == "__main__":
    import argparse

    print("[DEBUG] ========== 프로그램 시작 ==========")

    parser = argparse.ArgumentParser(
        description="한국 특허 명세서 자동 생성 파이프라인",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    # ── 입력 소스 (둘 중 하나만 사용) ───────────────────────
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--text",
        type=str,
        metavar="\"아이디어 텍스트\"",
        help="발명 아이디어를 텍스트로 직접 입력",
    )
    input_group.add_argument(
        "--pdf",
        type=str,
        metavar="path/to/patent.pdf",
        help="발명 아이디어가 담긴 PDF 파일 경로",
    )

    # ── 선택 옵션 ────────────────────────────────────────────
    parser.add_argument(
        "--output",
        type=str,
        default="data/out.txt",
        metavar="path/to/out.txt",
        help="생성된 명세서 저장 경로 (기본값: data/out.txt)",
    )
    parser.add_argument(
        "--num-fewshots",
        type=int,
        default=5,
        metavar="N",
        help="참조할 유사 특허 수 (기본값: 5)",
    )

    args = parser.parse_args()

    print(f"[DEBUG] 실행 모드  : {'PDF' if args.pdf else 'TEXT'}")
    print(f"[DEBUG] 출력 경로  : {args.output}")
    print(f"[DEBUG] Few-shot 수: {args.num_fewshots}")

    try:
        print("\n[DEBUG] ========== 모델 로드 시작 ==========")
        embedder = KorPatBERTEmbedder()
        searcher = PreComputedPatentSearcher(embedder, NPZ_PATH, JSON_PATH)
        pipeline = PatentGenerationPipeline(searcher, LLMClient())
        print("[DEBUG] ✅ 모델 및 파이프라인 초기화 완료")

        # ── ✅ --pdf / --text 분기 ────────────────────────────
        if args.pdf:
            pdf_path = args.pdf
            print(f"\n[DEBUG] PDF 입력 감지: {pdf_path}")

            if not Path(pdf_path).exists():
                print(f"[DEBUG] ❌ PDF 파일 없음: {pdf_path}")
                sys.exit(1)

            if not pdf_path.lower().endswith(".pdf"):
                print(f"[DEBUG] ❌ PDF 확장자가 아닙니다: {pdf_path}")
                sys.exit(1)

            print("[DEBUG] PDF 파싱 및 LLaVA 캡션 생성 중...")
            user_idea = parse_pdf_to_prompt_input(pdf_path)
            print(f"[DEBUG] ✅ PDF → prompt 변환 완료 ({len(user_idea)}자)")

        else:
            user_idea = args.text
            print(f"\n[DEBUG] 텍스트 입력 감지 ({len(user_idea)}자)")
            print(f"[DEBUG] 입력 미리보기: {user_idea[:80]}...")

        # ── 파이프라인 실행 ───────────────────────────────────
        print("\n[DEBUG] ========== 파이프라인 실행 시작 ==========")
        result = pipeline.run(user_idea, num_fewshots=args.num_fewshots)

        # ── 결과 출력 및 저장 ─────────────────────────────────
        print("\n" + "=" * 50 + "\n최종 생성 명세서\n" + "=" * 50)
        print(result)

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(result)

        print(f"\n[DEBUG] ✅ 결과 저장 완료: {output_path}")
        print("[DEBUG] ========== 프로그램 정상 완료 ==========")

    except FileNotFoundError as e:
        print(f"[DEBUG] ❌ 파일 없음: {e}")
        sys.exit(1)
    except Exception as e:
        import traceback
        print(f"[DEBUG] ❌ 오류 발생: {type(e).__name__}: {e}")
        traceback.print_exc()
        sys.exit(1)