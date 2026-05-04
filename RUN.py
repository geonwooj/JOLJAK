import os
import json
import re
import unicodedata
import torch
import numpy as np
import pandas as pd
from pathlib import Path
import faiss
import sys
from transformers import AutoModel
from models.KorPatBERT.korpat_tokenizer import Tokenizer # 사용자 제공 경로

from aimodule.llm_client import LLMClient
from aimodule.parsing.section_text_preprocess import (
    normalize_text_basic,
    preprocess_section_text,
    _normalize_desc_text
)
from aimodule.parsing.section_centering import l2_normalize_rows, apply_centering


DATA_ROOT = "data"
PROCESSED_DIR = os.path.join(DATA_ROOT, "reprocessed")
MODEL_PATH = Path("models/KorPatBERT/pytorch")
VOCAB_PATH = MODEL_PATH.parent / "pretrained" / "korpat_vocab.txt"
NPZ_PATH = Path("data/npz_backup_v1_desc_full_minus_background_centering_dynamic_weight")
JSON_PATH = Path("data/reprocessed")
# --- 1. KorPatBERT 임베딩 엔진 ---
class KorPatBERTEmbedder:
    def __init__(self, model_path, vocab_path):
        self.tokenizer = Tokenizer(vocab_path=vocab_path, cased=True)
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = AutoModel.from_pretrained(model_path).to(self.device)
        self.model.eval()
        self.domain = "Ai"
        print(f"[정보] KorPatBERT 모델이 {self.device}에 로드되었습니다.")
    
    def clean_query(self, text, section="abstract", mode="strong"):
        if not text: return ""
        text = normalize_text_basic(text)
        if section == "description":
            text = _normalize_desc_text(text)
        
        try:
            return preprocess_section_text(
                text=text, section=section, domain=self.domain, mode=mode
            )
        except:
            return text
    def embed(self, text, section="abstract"):
        cleaned_text = self.clean_query(text, section=section)
        tokens, _ = self.tokenizer.encode(cleaned_text, max_len=10000)
        if not tokens: return np.zeros(768)

        chunks = [tokens[i:i+512] for i in range(0, len(tokens), 512)][:30]
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
        
        return l2_normalize_rows(final_vec.reshape(1, -1))[0]

# --- 2. Pre-computed .npz 기반 검색 엔진 ---
class PreComputedPatentSearcher:
    def __init__(self, embedder, root_path, metadata_root):
        self.embedder = embedder
        self.root_path = Path(root_path)
        self.metadata_root = Path(metadata_root)
        
        # 도메인별/섹션별 데이터를 담을 캐시
        self.domain_data = {} 
        self.current_domain = None
        self.system_separation = 0.1    
    def _load_domain_assets(self, domain):
        if domain == self.current_domain:
            return
            
        print(f"[시스템] {domain} 도메인 전용 자산 분석 중...")
        centered_dir = self.root_path / "selected_centered_sections"
        
        assets = {}
        # 2. 통합 검색용 인덱스 로드
        final_dir = self.root_path / "final_vectors"
        final_path = final_dir / "final_dynamic_global__center-section__source-x__v1_desc_full_minus_background_centering_dynamic_weight.npz"

        final_data = np.load(final_path, allow_pickle=True)
        self.vectors = final_data['vectors'].astype('float32')
        self.doc_ids = final_data['doc_ids']
        self.labels = final_data['labels']
        meta = final_data['meta'].item()
        meta_data = json.loads(meta)
        meta_data = meta_data.get("weights", {})
        for section in ['abstract', 'claims', 'description']:
            pattern = f"{domain}__{section}__best-*.npz"
            matches = list(centered_dir.glob(pattern))
            sectioned_weights = meta_data.get(section, 0.33)
            if matches:
                filename = matches[0].name
                mode = filename.split('__best-')[1].split('__')[0]
                
                data = np.load(matches[0], allow_pickle=True)
                vecs = data['vectors'].astype('float32')
                
                assets[section] = {
                    'center': np.mean(vecs, axis=0),
                    'mode': mode,
                    'W': sectioned_weights, 
                }
                print(f"  - {section}: 모드 '{mode}' 적용 완료")
        # FAISS 인덱스 갱신
        self.index = faiss.IndexFlatIP(768)
        self.index.add(l2_normalize_rows(self.vectors))
        
        self.domain_assets = assets
        self.current_domain = domain
    def search(self, sectioned_input, k=10):
        domain = sectioned_input.get('type', 'Ai')
        self._load_domain_assets(domain)
        
        # 1. 섹션별 최적 모드로 임베딩 + 센터링
        v_abs = self.embedder.embed(sectioned_input['abstract']['clean'], section='abstract')
        if 'abstract' in self.domain_assets:
            v_abs = apply_centering(v_abs, self.domain_assets['abstract']['center'], renorm=True)
            w_abs = self.domain_assets['abstract'].get('W', 0.33) # 파일에서 가져온 가중치
        else: w_abs = 0.0

        # Claims
        v_clm = self.embedder.embed(sectioned_input['claims']['clean'], section='claims')
        if 'claims' in self.domain_assets:
            v_clm = apply_centering(v_clm, self.domain_assets['claims']['center'], renorm=True)
            w_clm = self.domain_assets['claims'].get('W', 0.33) # 파일에서 가져온 가중치
        else: w_clm = 0.0

        # Description
        v_dsc = self.embedder.embed(sectioned_input['description']['clean'], section='description')
        if 'description' in self.domain_assets:
            v_dsc = apply_centering(v_dsc, self.domain_assets['description']['center'], renorm=True)
            w_dsc = self.domain_assets['description'].get('W', 0.33) # 파일에서 가져온 가중치
        else: w_dsc = 0.0
        
        # 2. 동적 가중치 결합
        combined_query = (v_abs * w_abs) + (v_clm * w_clm) + (v_dsc * w_dsc)
        final_query = l2_normalize_rows(combined_query.reshape(1, -1))
        print(f"[시스템] 동적 가중치 적용: Abs({w_abs:.2f}), Clm({w_clm:.2f}), Dsc({w_dsc:.2f})")
        # 3. FAISS 검색
        distances, indices = self.index.search(final_query, k)
        
        results = []
        for i, idx in enumerate(indices[0]):
            doc_id = self.doc_ids[idx]
            domain = self.labels[idx]
            # 검색 결과 구성
            results.append({
                "doc_id": doc_id,
                "score": float(distances[0][i]),
                "text": self._load_original_text(doc_id, domain),
                "separation": self.system_separation,
                "domain": self.labels[idx] # 검색된 문서의 실제 도메인
            })
        return results

    def _load_original_text(self, doc_id, domain):
        target_file = self.metadata_root / domain / f"{doc_id}.json"
        
        if target_file.exists():
            with open(target_file, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            # 혹시 모를 예외 상황 (폴더명이 다를 경우 등)을 위해 전체 순회 백업
            print(f"[경고] {domain} 폴더에 {doc_id}가 없음. 전체 검색 시작...")
            for domain_folder in self.metadata_root.iterdir():
                if domain_folder.is_dir():
                    backup_file = domain_folder / f"{doc_id}.json"
                    if backup_file.exists():
                        with open(backup_file, "r", encoding="utf-8") as f:
                            return json.load(f)
        return {}

# --- 3. 최종 파이프라인 (Prompting & Orchestration) ---
class PatentGenerationPipeline:
    def __init__(self, searcher, llm_client):
        self.searcher = searcher
        self.llm = llm_client

    def split_input_sections(self, raw_input):
        """사용자 입력을 섹션별 JSON으로 분리하는 프롬프트"""
        system = """너는 한국어 특허 문서 구조화 및 임베딩 전처리 보조 LLM이다."""
        prompt = f"""
        
사용자가 입력한 발명 아이디어 또는 기술 설명을 분석하여, 특허 검색용 JSON으로 변환하라.
출력은 반드시 valid JSON 형식만 사용하고, JSON 바깥에 설명을 쓰지 마라.

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
        response = self.llm.call(system, prompt)
        try:
            res_json = json.loads(re.search(r'\{.*\}', response, re.S).group())
            return res_json
        except:
            return {"type": "Ai", "abstract": {"raw": raw_input, "clean": raw_input}, "claims": {"raw":"", "clean":""}, "description": {"raw":"", "clean":""}}
    def run(self, user_input, num_fewshots=5):
        # 1. 섹션화 및 검색
        sectioned_input = self.split_input_sections(user_input)
        raw_results = self.searcher.search(sectioned_input, k=num_fewshots)
        
        few_shots = []
        print(f"\n[Dynamic Search Report - filtering applied]")
        
        # 안전장치 기준 설정
        MIN_SCORE_THRESHOLD = 0.1  # 이 점수보다 낮으면 유사도가 없다고 판단
        MAX_GAP_THRESHOLD = 0.05    # 1위 특허와 점수 차이가 이보다 크면 관련성 급락으로 판단
        
        top_score = raw_results[0]['score'] if raw_results else 0

        for i, res in enumerate(raw_results):
            score = res['score']
            gap = top_score - score
            
            # [안전장치 1] 최소한의 유사도 검사
            if score < MIN_SCORE_THRESHOLD and len(few_shots) >= 2:
                print(f"  - {i+1}번 제외: 점수 미달 ({score:.4f} < {MIN_SCORE_THRESHOLD})")
                continue
                
            # [안전장치 2] 1위와의 격차 검사 (너무 동떨어진 기술 제외)
            if gap > MAX_GAP_THRESHOLD and len(few_shots) >= 2:
                print(f"  - {i+1}번 제외: 1위와 유사도 격차 너무 큼 (Gap: {gap:.4f})")
                continue
            
            # 통과된 데이터 추가
            few_shots.append(res)
            print(f"{len(few_shots)}. [{res['doc_id']}] Score: {score:.4f} (Selected)")
            data = res.get("text").get("abstract")[:100] + "..."
            print(f"요약 : {data}")
            # 토큰 효율을 위해 설정한 개수 도달 시 종료
            if len(few_shots) >= num_fewshots:
                break
        
        # 2. 명세서 생성
        final_prompt = self._build_final_prompt(sectioned_input, few_shots)
        system = "당신은 대한민국 최고 수준의 특허 변리사입니다."
        
        print(f"\n[시스템] 검증된 {len(few_shots)}개의 사례를 바탕으로 명세서를 생성합니다.")
        return self.llm.call(system, final_prompt)
    def _build_final_prompt(self, input_json, few_shots):
        """Few-shot 데이터들을 프롬프트에 구조적으로 배치"""
        examples_str = ""
        for i, fs in enumerate(few_shots):
            text_obj = fs.get('text', {})
            
            # 데이터 추출 (우선순위: clean > raw)
            abstract = text_obj.get('abstract', '내용 없음')
            claims = text_obj.get('claims', '내용 없음')
            
            # 토큰 절약을 위해 너무 긴 텍스트는 일부 절삭
            abstract_snip = abstract[:600] + ("..." if len(abstract) > 600 else "")
            
            examples_str += f"""
### [참고 유사 사례 {i+1}]
- 문서번호: {fs['doc_id']}
- 유사도 점수: {fs['score']:.4f}
- 발명의 요약: {abstract_snip}
- 핵심 청구범위: {claims}
"""
        
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
3. 출력은 반드시 [발명의 명칭], [특허청구범위], [발명의 설명] 섹션을 포함해야 합니다.
4. 명세서 작성이 끝난 후, '원하시면 ~해 드릴 수 있습니다'와 같은 추가 제안이나 후속 작업을 묻는 문장을 절대 포함하지 마십시오. 답변은 명세서 본문으로만 끝맺음하십시오.
"""

# --- 실행 예시 ---
if __name__ == "__main__":
    # 1. 명령행 인자 확인
    if len(sys.argv) < 2:
        print("\n[사용법] python RUN.py \"사용자 발명 아이디어 내용\"")
        print("예: python RUN.py \"딥러닝을 이용한 이미지 분석 시스템\"")
        sys.exit(1)
        
    # 2. 초기화
    user_idea = " ".join(sys.argv[1:])
    print(f"\n[실행] 입력된 아이디어: {user_idea[:50]}...")
    
    embedder = KorPatBERTEmbedder(MODEL_PATH, VOCAB_PATH)
    searcher = PreComputedPatentSearcher(
        embedder=embedder, 
        root_path=NPZ_PATH,
        metadata_root=JSON_PATH
    )
    pipeline = PatentGenerationPipeline(searcher, LLMClient())
    
    # 2. 실행
    result = pipeline.run(user_idea)
    print("\n" + "="*50)
    print("최종 생성 명세서")
    print("="*50)
    print(result)