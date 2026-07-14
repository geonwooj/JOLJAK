import os, json, re, unicodedata, torch, numpy as np
from pathlib import Path
from typing import Optional
import requests, sys, fitz, tempfile
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
import matplotlib
matplotlib.use("Agg")  # GUI 없는 서버 환경에서도 동작
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.gridspec import GridSpec

import time as _time
from contextlib import contextmanager
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

WEB_LINK           = "http://localhost:8080/api/signal/"
DATA_ROOT          = "data"
MODEL_PATH         = Path("models/KorPatBERT/pytorch")
VOCAB_PATH         = MODEL_PATH.parent / "pretrained" / "korpat_vocab.txt"
HF_MODEL_DIR       = str(MODEL_PATH)
NPZ_PATH           = Path("data/npz_korpat_rebuilt")
JSON_PATH          = Path("data/reprocessed")
FEW_SHOT_PATH      = Path("data")
RUN_OUTPUT_DIR     = Path("data/run_outputs")   # phase별 중간 산출물 저장 위치

CHUNK_SIZE         = 256
STRIDE             = 256
MAX_CHUNKS         = 8
PREPROCESS_VERSION = "v2_korpat_rebuilt"

PDF_IMAGE_MIN_WIDTH  = 100
PDF_IMAGE_MIN_HEIGHT = 100
PDF_MAX_IMAGES       = 5

NUM_AGENT_RUNS       = 5      # Phase 2 독립 생성 횟수
CLUSTER_SIM_THRESHOLD = 0.55   # 같은 의미 클러스터로 묶는 코사인 유사도 임계값

DOMAIN_BASELINES = {
    "Ai":            {"intra_mean": 0.1746, "inter_mean": -0.0339,
                      "p25": 0.0697, "p75": 0.2809, "p90": 0.3662},
    "BigData":       {"intra_mean": 0.2293, "inter_mean": -0.0326,
                      "p25": 0.1228, "p75": 0.3336, "p90": 0.4207},
    "InfoComm":      {"intra_mean": 0.0765, "inter_mean": -0.0372,
                      "p25": -0.0991, "p75": 0.2063, "p90": 0.3781},
    "Semiconductor": {"intra_mean": 0.4408, "inter_mean": -0.1676,
                      "p25": 0.2974, "p75": 0.5649, "p90": 0.7355},
}

CLAIMS_STOPWORDS_CONSERVATIVE = [
    "상기", "포함하는", "포함하고", "구비하는", "구비하고",
    "방법으로서", "장치에 있어서", "컴퓨팅 장치에서 수행되는 방법으로서",
    "하나 이상의 프로세서들", "하나 이상의 프로그램들", "메모리를 구비하고",
]
CLAIMS_STOPWORDS_STRONG = [
    "제 1 항에 있어서", "제1항에 있어서",
    "제 2 항에 있어서", "제2항에 있어서",
    "제 3 항에 있어서", "제3항에 있어서",
    "삭제", "단계", "수단", "모듈", "복수의",
]
DOMAIN_KEYWORDS = {
    "Ai":            ["인공지능", "딥러닝", "머신러닝", "신경망", "학습모델",
                      "강화학습", "자연어처리", "이미지인식"],
    "BigData":       ["빅데이터", "분산처리", "하둡", "스파크", "데이터레이크",
                      "데이터웨어하우스", "스트리밍", "배치처리"],
    "InfoComm":      ["통신", "네트워크", "프로토콜", "패킷", "무선",
                      "기지국", "단말기", "송수신"],
    "Semiconductor": ["반도체", "트렌치", "도핑", "에칭", "산화막",
                      "웨이퍼", "포토리소그래피", "게이트"],
}

def extract_generated_indep_claim(final_claims_text: str) -> str:
    """
    Phase 3 Area Chair 출력(final_claims.txt)에서 최종 독립항 추출.

    Area Chair 출력 형식:
        [2. 최종 독립항]
        제1항. ...
        [3. 종속항 계층]
        ...

    이 형식은 "청구항 N" 헤더가 아니라 "제N항." 형식이므로
    split_claims_into_items()로는 독립항을 정확히 추출할 수 없다.
    """
    # 1순위: "[2. 최종 독립항]" 섹션 → "제1항." 본문 추출
    m = re.search(
        r"\[2\.\s*최종\s*독립항\](.*?)(?=\[3\.\s*종속항|\Z)",
        final_claims_text, re.S
    )
    if m:
        block = m.group(1).strip()
        m2 = re.search(r"제\s*1\s*항\s*[\.．]?\s*(.+)", block, re.S)
        if m2:
            text = m2.group(1).strip()
            # 제2항 시작 전까지만
            m3 = re.search(r"\n제\s*[2-9]\s*항", text)
            if m3:
                text = text[:m3.start()].strip()
            return text

    # 2순위: 전체 텍스트에서 "제1항." 패턴 탐색
    m = re.search(
        r"제\s*1\s*항\s*[\.．]?\s*(.+?)(?=\n제\s*[2-9]\s*항|\Z)",
        final_claims_text, re.S
    )
    if m:
        return m.group(1).strip()

    # 3순위: fallback — split_claims_into_items
    items = split_claims_into_items(final_claims_text)
    for item in items:
        if item["is_independent"]:
            return item["text"]
    return items[0]["text"] if items else ""

def verify_domain(raw_input: str, classified_domain: str) -> str:
    """
    Phase 0 LLM 분류 도메인을 원문 키워드 기반으로 교차 검증.

    LLM이 PDF 파싱 텍스트를 잘못된 도메인으로 분류하면
    이후 모든 Phase의 NPZ 검색/임베딩 기준이 통째로 틀어지므로,
    원문에 등장하는 도메인별 키워드 점수로 2차 검증한다.

    키워드가 전혀 없으면(판별 불가) LLM 분류를 그대로 신뢰하고,
    키워드 기반 최고점 도메인이 LLM 분류와 다르면 override한다.
    """
    keyword_scores = {
        domain: sum(1 for kw in keywords if kw in raw_input)
        for domain, keywords in DOMAIN_KEYWORDS.items()
    }

    best_kw_domain = max(keyword_scores, key=keyword_scores.get)
    best_score     = keyword_scores[best_kw_domain]

    if best_score == 0:
        print(f"[Phase0] 키워드 기반 도메인 판별 불가 (점수 0) "
              f"→ LLM 분류 '{classified_domain}' 유지")
        return classified_domain

    if best_kw_domain != classified_domain:
        print(f"[Phase0] ⚠️  도메인 불일치 감지!")
        print(f"  LLM 분류:    {classified_domain}")
        print(f"  키워드 기반: {best_kw_domain} "
              f"(점수: {best_score}, 전체: {keyword_scores})")
        print(f"  → 키워드 기반 도메인으로 override: {best_kw_domain}")
        return best_kw_domain

    print(f"[Phase0] ✓ 도메인 교차검증 일치: {classified_domain} "
          f"(키워드 점수: {best_score})")
    return classified_domain
# ════════════════════════════════════════════════════════════════
# 한글 폰트 자동 감지
# ════════════════════════════════════════════════════════════════
def setup_korean_font() -> bool:
    candidates = ["Malgun Gothic", "AppleGothic", "NanumGothic",
                 "NanumBarunGothic", "Noto Sans CJK KR"]
    available = {f.name for f in fm.fontManager.ttflist}
    for name in candidates:
        if name in available:
            plt.rcParams["font.family"] = name
            plt.rcParams["axes.unicode_minus"] = False
            print(f"[Chart] 한글 폰트 적용: {name}")
            return True
    print("[Chart] ⚠️  한글 폰트를 찾지 못함 → 영문 라벨로 대체")
    return False


KOREAN_FONT_OK = setup_korean_font()


def L(kor: str, eng: str) -> str:
    return kor if KOREAN_FONT_OK else eng

# ════════════════════════════════════════════════════════════════
# 공통 유틸
# ════════════════════════════════════════════════════════════════
def send_signal(code: int, description: str = ""):
    """
    백엔드에 진행 상황 시그널을 전송.
    실패해도, 느려도 파이프라인 진행에 영향이 없도록
    백그라운드 스레드에서 fire-and-forget으로 전송한다.
    """
    def _send():
        try:
            requests.post(f"{WEB_LINK}{code}", timeout=2)
            print(f"[Signal] {code} 전송 완료" + (f" — {description}" if description else ""))
        except Exception as e:
            print(f"[Signal] {code} 전송 실패 (무시): {e}")

    threading.Thread(target=_send, daemon=True).start()
        
class StageTimer:
    """
    파이프라인 각 단계의 소요 시간을 기록.
    """

    def __init__(self):
        self.records: OrderedDict[str, dict] = OrderedDict()
        self._pipeline_start = None

    def start_pipeline(self):
        self._pipeline_start = _time.perf_counter()
        print(f"\n[Timer] 파이프라인 시작 — {_time.strftime('%H:%M:%S')}")

    @contextmanager
    def stage(self, name: str, parent: Optional[str] = None):
        """
        with timer.stage("Phase 1"): ... 형태로 사용.
        """
        t0 = _time.perf_counter()
        ts = _time.strftime("%H:%M:%S")
        print(f"[Timer] ▶ {name} 시작  ({ts})")
        try:
            yield
        finally:
            elapsed = _time.perf_counter() - t0
            self.records[name] = {"elapsed": elapsed, "parent": parent,
                                  "start_ts": ts}
            print(f"[Timer] ◀ {name} 완료  (+{elapsed:.2f}s)")

    
    def mark(self, name: str, elapsed: float, parent: Optional[str] = None,
            is_parallel: bool = False):
        """
        반복 호출을 누적 기록.
        """
        if name not in self.records:
            self.records[name] = {"elapsed": 0.0, "parent": parent,
                                  "start_ts": _time.strftime("%H:%M:%S"),
                                  "count": 0, "is_parallel": is_parallel,
                                  "individual_times": []}
        self.records[name]["elapsed"] += elapsed
        self.records[name]["count"] = self.records[name].get("count", 0) + 1
        self.records[name]["individual_times"].append(elapsed)
        self.records[name]["is_parallel"] = is_parallel

    @contextmanager
    def sub(self, name: str, parent: str):
        """반복되는 하위 작업(예: 문서별 LLM 호출, agent별 생성)의 개별 호출 시간 측정."""
        t0 = _time.perf_counter()
        try:
            yield
        finally:
            elapsed = _time.perf_counter() - t0
            self.mark(name, elapsed, parent=parent)

    def print_summary(self):
        if self._pipeline_start is None:
            print("[Timer] 시작 기록 없음")
            return

        total = _time.perf_counter() - self._pipeline_start

        print(f"\n{'='*78}")
        print(f"[Timer] 전체 실행 시간 요약  (총 {total:.2f}초, 벽시계 기준)")
        print(f"{'='*78}")
        print(f"{'단계':<35} {'경과(초)':>10} {'비중':>7} {'호출':>5}  {'비고'}")
        print(f"{'-'*78}")

        top_level = [(k, v) for k, v in self.records.items() if v.get("parent") is None]
        for name, info in top_level:
            elapsed = info["elapsed"]
            pct = (elapsed / total * 100) if total > 0 else 0
            cnt = info.get("count", "-")
            print(f"{name:<35} {elapsed:>10.2f} {pct:>6.1f}% {cnt!s:>5}")

            children = [(k, v) for k, v in self.records.items()
                       if v.get("parent") == name]
            for cname, cinfo in children:
                celapsed = cinfo["elapsed"]
                ccnt = cinfo.get("count", "-")
                times = cinfo.get("individual_times", [])
                is_par = cinfo.get("is_parallel", False)

                if is_par and times:
                    # 병렬 작업: 비중(%) 대신 합산시간/최대시간/평균시간을 보여줌
                    avg = celapsed / ccnt if ccnt else 0
                    max_t = max(times)
                    min_t = min(times)
                    print(f"  └ {cname:<31} {'(병렬)':>10} {'':>7} {ccnt!s:>5}  "
                          f"합산={celapsed:.1f}s 최대={max_t:.1f}s 최소={min_t:.1f}s 평균={avg:.1f}s")
                else:
                    cpct = (celapsed / total * 100) if total > 0 else 0
                    avg_str = f" (평균 {celapsed/ccnt:.2f}s)" if isinstance(ccnt, int) and ccnt > 0 else ""
                    print(f"  └ {cname:<31} {celapsed:>10.2f} {cpct:>6.1f}% {ccnt!s:>5}{avg_str}")

        print(f"{'-'*78}")
        print(f"{'총합(벽시계 기준)':<35} {total:>10.2f} {'100.0%':>7}")
        print(f"{'='*78}\n")

        if top_level:
            slowest = max(top_level, key=lambda x: x[1]["elapsed"])
            pct = slowest[1]["elapsed"] / total * 100 if total > 0 else 0
            print(f"[Timer] 가장 오래 걸린 단계: {slowest[0]} "
                  f"({slowest[1]['elapsed']:.2f}s, 전체의 {pct:.1f}%)")

        # 병렬화 효과 요약
        parallel_stages = [(k, v) for k, v in self.records.items()
                           if v.get("is_parallel") and v.get("individual_times")]
        if parallel_stages:
            print(f"\n[Timer] 병렬화 효과:")
            for name, info in parallel_stages:
                times = info["individual_times"]
                seq_estimate = sum(times)          # 순차 실행했다면 걸렸을 시간
                actual_max = max(times)             # 병렬 실행 시 실제 소요(가장 느린 작업)
                speedup = seq_estimate / actual_max if actual_max > 0 else 0
                print(f"  {name.strip('  - ')}: 순차 추정 {seq_estimate:.1f}s → "
                      f"병렬 실제 {actual_max:.1f}s  ({speedup:.1f}배 단축)")
def robust_json_parse(text: str) -> Optional[dict]:
    text = re.sub(r"```(?:json)?", "", text).strip()
    start = text.find("{")
    if start == -1:
        return None
    depth, end = 0, -1
    for i, ch in enumerate(text[start:], start):
        if ch == "{":   depth += 1
        elif ch == "}": depth -= 1
        if depth == 0:
            end = i
            break
    if end == -1:
        return None
    candidate = text[start:end + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        candidate = re.sub(r"[\x00-\x1f\x7f](?<![\n\t])", "", candidate)
        try:
            return json.loads(candidate)
        except Exception:
            return None


def load_npz_pack(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"NPZ not found: {path}")
    with np.load(path, allow_pickle=True) as z:
        meta = {}
        if "meta" in z:
            try:
                meta = json.loads(str(z["meta"].item()))
            except Exception:
                pass
        return {
            "vectors": z["vectors"].astype(np.float32),
            "labels":  z["labels"].astype(str).tolist(),
            "doc_ids": z["doc_ids"].astype(str).tolist(),
            "meta":    meta,
        }


def _score_label(sc: float, domain: str) -> str:
    b = DOMAIN_BASELINES.get(domain, {})
    if   sc >= b.get("p90", 1):         return "★★ 매우 유사 (상위10%)"
    elif sc >= b.get("intra_mean", 1):  return "★  평균 이상"
    elif sc >= b.get("p25", 1):         return "○  평균 이하 (참고)"
    elif sc >= b.get("inter_mean", -1): return "△  노이즈 경계"
    else:                                return "✗  노이즈 (무의미)"


def extract_independent_claim(claims_text: str) -> str:
    m = re.search(r"(청구항\s*2|제\s*2\s*항에\s*있어서)", claims_text)
    return claims_text[:m.start()].strip() if m else claims_text[:700].strip()


def split_claims_into_items(claims_text: str) -> list:
    """
    전체 청구항 텍스트를 항 단위로 분리.

    핵심 문제: 종속항 본문에 "청구항 N에 있어서"라는 인용구가
    줄 맨 앞에서 시작하는 경우가 있어, 단순 "줄 시작 + 청구항 N" 매치만으로는
    이 인용구를 진짜 헤더와 구분할 수 없다.
    (예: "청구항 2\n청구항 1에 있어서, ..." → "청구항 1에 있어서"도
     줄 맨 앞에서 "청구항 N" 패턴과 매치되어 잘못된 분할 지점이 됨)

    해결: "청구항 N" 바로 뒤(공백 포함)에 "에 있어서"가 오면
    이는 인용구이지 헤더가 아니므로 negative lookahead로 제외한다.
    진짜 헤더는 "청구항 N" 뒤에 줄바꿈이 오거나, 공백 후 다른 문장이 이어진다.
    """
    if not claims_text or not claims_text.strip():
        return []

    # "청구항 N" 뒤에 "에 있어서"가 바로 오지 않는 경우만 헤더로 인정
    pattern = re.compile(
        r"^청구항\s*(\d+)(?!\s*에\s*있어서)",
        re.MULTILINE
    )
    matches = list(pattern.finditer(claims_text))

    if not matches:
        return [{"claim_no": 1, "text": claims_text.strip(), "is_independent": True}]

    items = []
    for i, m in enumerate(matches):
        start = m.end()
        end   = matches[i+1].start() if i+1 < len(matches) else len(claims_text)
        claim_no   = int(m.group(1))
        claim_text = claims_text[start:end].strip()

        if not claim_text:
            continue

        stripped = re.sub(r"[\(\)\[\]\s\.,:：]", "", claim_text)
        if stripped in ("삭제",) or (len(stripped) <= 3 and "삭제" in stripped):
            continue

        is_dependent = bool(re.search(r"제\s*\d+\s*항에\s*있어서", claim_text))
        items.append({"claim_no": claim_no, "text": claim_text,
                      "is_independent": not is_dependent})
    return items

def preprocess_single_claim(text: str, mode: str = "x") -> str:
    text = cleanup_artifacts(text, "claims")
    if mode == "x":
        return text
    for phrase in CLAIMS_STOPWORDS_CONSERVATIVE:
        text = text.replace(phrase, " ")
    if mode == "strong":
        for phrase in CLAIMS_STOPWORDS_STRONG:
            text = text.replace(phrase, " ")
    return re.sub(r"\s+", " ", text).strip()


# ════════════════════════════════════════════════════════════════
# KorPatBERTEmbedder
# ════════════════════════════════════════════════════════════════
class KorPatBERTEmbedder:
    """
    KorPatBERT 기반 임베딩 엔진.
    이 클래스는 단순 텍스트 전처리기가 아니라, 사용자 입력을
    임베딩 공간(768차원, DB와 동일 좌표계)으로 투영하는 역할을 한다.
    Phase 1의 "재구조화"와 Phase 2의 "클러스터링"이 모두 이 투영 결과 위에서
    수행되므로, 이 단계의 정확성이 이후 모든 phase의 신뢰도를 결정한다.
    """
    def __init__(self):
        self.device      = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.max_seq_len = CHUNK_SIZE
        if not VOCAB_PATH.exists():
            raise FileNotFoundError(f"Vocab not found: {VOCAB_PATH}")
        self.tokenizer   = Tokenizer(vocab_path=str(VOCAB_PATH), cased=True)
        self.model       = AutoModel.from_pretrained(
            HF_MODEL_DIR, local_files_only=True).to(self.device)
        self.model.eval()
        self.hidden_size = self.model.config.hidden_size
        print(f"[Embedder] device={self.device}  hidden={self.hidden_size}")

    def embed_text(self, text: str) -> np.ndarray:
        if not text or not text.strip():
            return np.zeros(self.hidden_size, dtype=np.float32)
        try:
            token_ids, _ = self.tokenizer.encode(text, max_len=None)
        except Exception as e:
            print(f"[Embedder] 토큰화 실패: {e}")
            return np.zeros(self.hidden_size, dtype=np.float32)

        actual  = token_ids[1:-1]
        max_len = self.max_seq_len - 2
        chunks  = [actual[i:i+max_len]
                   for i in range(0, len(actual), STRIDE)][:MAX_CHUNKS]

        cls_id = self.tokenizer._token_dict[self.tokenizer._token_cls]
        sep_id = self.tokenizer._token_dict[self.tokenizer._token_sep]
        embedded = []

        with torch.no_grad():
            for chunk in chunks:
                ids  = [cls_id] + chunk + [sep_id]
                mask = [1] * len(ids)
                pad  = self.max_seq_len - len(ids)
                if pad > 0:
                    ids  += [self.tokenizer._pad_index] * pad
                    mask += [0] * pad
                out = self.model(
                    input_ids      = torch.tensor([ids]).to(self.device),
                    attention_mask = torch.tensor([mask]).to(self.device),
                ).last_hidden_state[0].detach().cpu().numpy()
                m = np.array(mask, dtype=np.float32)[:, None]
                embedded.append((out * m).sum(0) / np.clip(m.sum(), 1, None))

        if not embedded:
            return np.zeros(self.hidden_size, dtype=np.float32)
        v = np.mean(np.stack(embedded), axis=0)
        return (v / (np.linalg.norm(v) + 1e-8)).astype(np.float32)


# ════════════════════════════════════════════════════════════════
# ClaimsOnlySearcher (claims 섹션 단독 검색 + 항별 검색)
# ════════════════════════════════════════════════════════════════
class ClaimsOnlySearcher:
    def __init__(self, embedder: KorPatBERTEmbedder,
                 npz_root=NPZ_PATH, metadata_root=JSON_PATH):
        self.embedder      = embedder
        self.npz_root      = Path(npz_root)
        self.metadata_root = Path(metadata_root)
        self._cache        = {}

    def _load_domain(self, domain: str):
        if domain in self._cache:
            return

        final_path = (
            self.npz_root / "final_vectors" /
            f"final_dynamic_by_domain__center-section__source-x__{PREPROCESS_VERSION}.npz"
        )
        meta      = load_npz_pack(final_path)["meta"]
        best_mode = meta.get("best_modes", {}).get("claims", "x")

        sec_path = (
            self.npz_root / "selected_centered_sections" /
            f"{domain}__claims__best-{best_mode}__center-section__{PREPROCESS_VERSION}.npz"
        )
        if not sec_path.exists():
            raise FileNotFoundError(f"claims NPZ 없음: {sec_path}")
        sec_data = load_npz_pack(sec_path)

        bank_path = (
            self.npz_root / "domain_section_mode_banks" /
            f"{domain}__claims__x__"
            f"desc-full_minus_background__"
            f"tok{CHUNK_SIZE}-{STRIDE}-{MAX_CHUNKS}__{PREPROCESS_VERSION}.npz"
        )
        if bank_path.exists():
            bank_data = load_npz_pack(bank_path)
            center = np.mean(bank_data["vectors"], axis=0,
                             keepdims=True).astype(np.float32)
        else:
            center = np.mean(sec_data["vectors"], axis=0,
                             keepdims=True).astype(np.float32)
            print(f"  [ClaimsSearcher] bank 없음 → centroid 근사")

        self._cache[domain] = {
            "vectors":  sec_data["vectors"].astype(np.float32),
            "doc_ids":  sec_data["doc_ids"],
            "center":   center,
            "mode":     best_mode,
        }
        print(f"[ClaimsSearcher] '{domain}' 로드  "
              f"mode={best_mode}  docs={len(sec_data['doc_ids'])}")

    def embed_query_claim(self, claim_text: str, domain: str) -> np.ndarray:
        """단일 텍스트(전체 claims 혹은 항 1개) → centering 적용된 쿼리 벡터."""
        self._load_domain(domain)
        cached    = self._cache[domain]
        processed = preprocess_single_claim(claim_text, cached["mode"])
        raw_vec   = self.embedder.embed_text(processed)
        centered  = apply_centering(
            raw_vec.reshape(1, -1), cached["center"],
            alpha=1.0, renorm=True
        ).flatten()
        return l2_normalize_rows(centered.reshape(1, -1)).flatten()

    def search_by_vector(self, query_vec: np.ndarray, domain: str, k: int = 10) -> list:
        self._load_domain(domain)
        cached  = self._cache[domain]
        scores  = np.dot(cached["vectors"], query_vec)
        top_idx = np.argsort(scores)[::-1][:k]
        results = []
        for idx in top_idx:
            sc     = float(scores[idx])
            doc_id = cached["doc_ids"][idx]
            results.append({"doc_id": doc_id, "score": sc,
                            "label": _score_label(sc, domain)})
        return results


    def _convert_structured_to_items(self, claims_structured: dict) -> list:
        """
        JSON의 claims_structured({"청구항 1": "...", ...})를
        split_claims_into_items()와 동일한 형태로 변환.
        비정상적으로 긴 항(도면 목록 등이 섞인 마지막 항)은 절단한다.
        """
        MAX_SINGLE_CLAIM_LEN = 1500

        items = []
        for key, text in claims_structured.items():
            m = re.search(r'(\d+)', key)
            if not m:
                continue
            claim_no = int(m.group(1))
            text = text.strip()
            if not text:
                continue

            stripped = re.sub(r"[\(\)\[\]\s\.,:：]", "", text)
            if stripped in ("삭제",) or (len(stripped) <= 3 and "삭제" in stripped):
                continue

            if len(text) > MAX_SINGLE_CLAIM_LEN:
                cut_match = re.search(r"(도면\s*\d+[a-z]?\s*\n\s*도면\s*\d+)", text)
                if cut_match:
                    text = text[:cut_match.start()].strip()
                else:
                    text = text[:MAX_SINGLE_CLAIM_LEN].strip()

            is_dependent = bool(re.search(r"제\s*\d+\s*항에\s*있어서", text))
            items.append({"claim_no": claim_no, "text": text,
                          "is_independent": not is_dependent})

        items.sort(key=lambda x: x["claim_no"])
        return items


    def search(self, claims_text: str, domain: str, k: int = 10) -> list:
        """전체 claims 텍스트로 문서 단위 top-k 검색."""
        query_vec = self.embed_query_claim(claims_text, domain)
        top_results = self.search_by_vector(query_vec, domain, k=k)

        results = []
        for r in top_results:
            doc = self._load_doc(r["doc_id"], domain)
            claims_full = str(doc.get("claims", ""))

            # ── claims_structured 우선 사용 ──────────────────────────
            claims_structured = doc.get("claims_structured")
            if claims_structured and isinstance(claims_structured, dict):
                split_items = self._convert_structured_to_items(claims_structured)
            else:
                split_items = split_claims_into_items(claims_full)
            # ──────────────────────────────────────────────────────────

            results.append({
                **r,
                "title":            str(doc.get("title", ""))[:80],
                "abstract":         str(doc.get("abstract", ""))[:400],
                "independent_claim": split_items[0]["text"] if split_items else "",
                "claims_full":      claims_full,
                "claim_items":      split_items,
                "description":      str(doc.get("description", ""))[:600],
                "text":             doc,
            })
        return results

    def _load_doc(self, doc_id: str, domain: str) -> dict:
        path = self.metadata_root / domain / f"{doc_id}.json"
        if not path.exists():
            return {}
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}


# ════════════════════════════════════════════════════════════════
# Phase 1: 중간 문서 재구조화기
# ════════════════════════════════════════════════════════════════
class IntermediateDocumentRestructurer:
    """
    claims 검색 top-5 문서를 각각 LLM으로 재구조화.
    동시에 사용자 청구항(항 단위)과 해당 문서 청구항(항 단위) 간
    유사도를 계산하여, "가장 유사한 청구항 Top-5"를
    실제 KorPatBERT 점수로 산출한다(LLM 추정이 아님).

    핵심: 문서 유사도 순위(전체 claims 벡터 기준)와
          청구항 유사도 순위(항 단위 벡터 기준)는 서로 다른 정렬 기준이므로
          분리하여 별도로 계산하고 결과에 둘 다 포함한다.
    """

    def __init__(self, searcher: ClaimsOnlySearcher, llm_client):
        self.searcher = searcher
        self.llm      = llm_client

    def restructure_all(self, user_claim_items: list, top5_docs: list,
                    domain: str) -> list:
        results = []
        for doc_rank, doc in enumerate(top5_docs, 1):
            print(f"[Phase1] 문서 {doc_rank}/{len(top5_docs)} 재구조화 중: {doc['doc_id']}")

            sim_result = self._compute_claim_level_similarity(
                user_claim_items, doc, domain
            )
            claim_level_matches = sim_result["top5"]        # LLM 프롬프트용
            all_claim_pairs      = sim_result["all_pairs"]   # 시각화용 (전체)

            restructured_text = self._llm_restructure(doc, claim_level_matches)

            results.append({
                "doc_id":              doc["doc_id"],
                "doc_rank":            doc_rank,
                "doc_score":           doc["score"],
                "doc_label":           doc["label"],
                "restructured_text":   restructured_text,
                "claim_level_matches": claim_level_matches,   # LLM이 본 것 (top5)
                "all_claim_pairs":     all_claim_pairs,        # 시각화 전용 (전체)
            })
        return results


    def _compute_claim_level_similarity(self, user_claim_items: list,
                                    doc: dict, domain: str) -> dict:
        """
        반환: {"top5": [...], "all_pairs": [...]}
        top5      : LLM 재구조화 프롬프트에 넣을 상위 5개 (중복 없음, 점수 내림차순)
        all_pairs : 시각화(히트맵 등)에 사용할 전체 페어 (모든 사용자 청구항 포함)
        """
        doc_claim_items = doc.get("claim_items", [])
        if not user_claim_items or not doc_claim_items:
            return {"top5": [], "all_pairs": []}

        seen_pairs = set()
        pairs = []
        for u in user_claim_items:
            u_vec = self.searcher.embed_query_claim(u["text"], domain)
            for d in doc_claim_items:
                key = (u["claim_no"], d["claim_no"])
                if key in seen_pairs:
                    continue
                seen_pairs.add(key)

                d_vec = self.searcher.embed_query_claim(d["text"], domain)
                sc = float(np.dot(u_vec, d_vec))
                pairs.append({
                    "user_claim_no": u["claim_no"],
                    "doc_claim_no":  d["claim_no"],
                    "score":         sc,
                    "label":         _score_label(sc, domain),
                    "doc_claim_text": d["text"][:200],
                })

        pairs.sort(key=lambda p: p["score"], reverse=True)

        high_score_pairs = [p for p in pairs if p["score"] >= 0.45]
        if len(high_score_pairs) >= 3:
            flagged_claim = high_score_pairs[0]["user_claim_no"]
            print(f"  [경고] doc={doc.get('doc_id','?')}: 사용자 청구항{flagged_claim}이 "
                  f"{len(high_score_pairs)}개 문서 청구항과 0.45 이상으로 매칭됨. "
                  f"해당 청구항이 도메인 일반적 표현(허브성 텍스트)일 가능성을 점검하십시오.")

        max_pairs = len(user_claim_items) * len(doc_claim_items)
        top5 = pairs[: min(5, max_pairs)]

        return {"top5": top5, "all_pairs": pairs}   # ← all_pairs 추가 반환

    def _llm_restructure(self, doc: dict, claim_level_matches: list) -> str:
        """phase 1 프롬프트로 단일 문서를 재구조화."""
        claims_text = doc.get("claims_full", "")
        title       = doc.get("title", "")
        abstract    = doc.get("abstract", "")
        description = doc.get("description", "")

        doc_block = f"""제목: {title}
    요약: {abstract}
    청구항: {claims_text}
    도면/알고리즘 관련 설명: {description}
    """

        match_lines = []
        for m in claim_level_matches:
            match_lines.append(
                f"- 사용자 청구항{m['user_claim_no']} ↔ 문서 청구항{m['doc_claim_no']} "
                f"(유사도 {m['score']:.4f}, {m['label']})"
            )
        match_block = "\n".join(match_lines) if match_lines else "(계산된 유사 항 없음)"

        system = "당신은 특허 분석 전문가입니다."
        prompt = f"""아래 특허 문서를 청구항 생성에 최적화된 구조로 재구성하십시오.
    '''{doc_block}'''

    [참고: KorPatBERT로 사전 계산된 청구항 단위 유사도 — 반드시 이 수치를 그대로 인용하십시오]
    {match_block}

    위 목록은 이미 중복 없이 점수 내림차순으로 정렬되어 있으며, 총 {len(claim_level_matches)}개입니다.
    - 이 개수를 그대로 유지하십시오. 5개보다 적다면 적은 개수 그대로 출력하고,
      존재하지 않는 페어를 새로 만들어 5개로 채우지 마십시오.
    - 동일한 (사용자 청구항, 문서 청구항) 조합을 중복하여 출력하지 마십시오.

    다음 형식으로 출력하십시오:

    문서 제목:
    문서 요약: (3문장 이내)
    청구항 전체: (내부 종속항 포함 전체 나열)
    알고리즘 및 도면 설명 요약:
    가장 유사한 청구항 목록: (위에 제공된 유사도 수치를 그대로, 중복 없이, 있는 개수만큼만 인용)
    사용자 아이디어와 직접 충돌 가능한 청구항:
    사용자 아이디어와 구별되는 차별 구성요소:
    """
        return self.llm.call(system, prompt)
    def build_intermediate_summary(self, restructured_docs: list) -> str:
        """
        Phase 2 / Phase 3에 그대로 투입할 중간 구조화 문서 묶음 텍스트.
        문서 순위(doc_rank)와 청구항 유사도(claim_level_matches)를
        둘 다 명시하여, 두 정렬 기준이 다를 수 있음을 LLM이 인지하게 한다.
        """
        blocks = []
        for d in restructured_docs:
            blocks.append(
                f"=== [문서 순위 {d['doc_rank']}위 | doc_id={d['doc_id']} | "
                f"문서 전체 유사도={d['doc_score']:.4f} ({d['doc_label']})] ===\n"
                f"{d['restructured_text']}\n"
            )
        return "\n".join(blocks)

# ════════════════════════════════════════════════════════════════
# Phase 1 시각화 모듈
# ════════════════════════════════════════════════════════════════
class Phase1Visualizer:
    """
    Phase 1(중간 문서 재구조화) 결과를 matplotlib으로 시각화.
    [A] 문서 단위 유사도 막대그래프
    [C] 사용자 청구항 × 문서 최고유사도 히트맵
    두 그래프만 1x2로 배치. 그래프 내부는 "N번 문서"로 표기하고,
    실제 문서ID/요약은 그래프 하단 범례 텍스트로 별도 표시한다.
    """

    def __init__(self, output_dir: Path = RUN_OUTPUT_DIR):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _extract_doc_brief(self, doc: dict, max_len: int = 50) -> str:
        """
        restructured_text에서 "문서 요약:" 다음 내용을 뽑아 초간단 요약 생성.
        실패 시 title을 사용.
        """
        text = doc.get("restructured_text", "")

        m = re.search(r"문서\s*요약\s*[:：]\s*(.+?)(?=\n\s*\n|청구항\s*전체|$)",
                      text, re.S)
        if m:
            summary = m.group(1).strip()
            summary = re.sub(r"\s+", " ", summary)
            # 첫 문장만 사용 (마침표 기준)
            first_sentence = re.split(r"(?<=[.다])\s+", summary)[0]
            brief = first_sentence
        else:
            brief = ""

        if not brief:
            # fallback: 문서 제목 사용
            m2 = re.search(r"문서\s*제목\s*[:：]\s*(.+?)(?=\n)", text)
            brief = m2.group(1).strip() if m2 else doc.get("doc_id", "")

        if len(brief) > max_len:
            brief = brief[:max_len].rstrip() + "..."
        return brief

    def save_dashboard(self, restructured_docs: list, domain: str,
                       save_path: Optional[Path] = None) -> Path:
        if not restructured_docs:
            print("[Phase1Visualizer] 시각화할 문서 결과가 없습니다.")
            return None

        save_path = Path(save_path) if save_path else \
            (self.output_dir / "phase1_similarity_dashboard.png")
        save_path.parent.mkdir(parents=True, exist_ok=True)

        baseline = DOMAIN_BASELINES.get(domain, {})

        # 문서별 "N번 문서" 라벨 + 초간단 요약 매핑 생성
        doc_labels  = [L(f"{i+1}번 문서", f"Doc {i+1}") for i in range(len(restructured_docs))]
        doc_briefs  = [self._extract_doc_brief(d) for d in restructured_docs]

        fig = plt.figure(figsize=(15, 8.5))
        gs  = GridSpec(1, 2, figure=fig, wspace=0.28,
                       left=0.06, right=0.97, top=0.86, bottom=0.34)
        ax_a = fig.add_subplot(gs[0, 0])
        ax_c = fig.add_subplot(gs[0, 1])

        fig.suptitle(
            L(f"Phase 1: 청구항 검색 유사도 분석 — 도메인: {domain}",
              f"Phase 1: Claim Search Similarity — Domain: {domain}"),
            fontsize=15, fontweight="bold", y=0.96
        )

        self._plot_doc_level_bar(ax_a, restructured_docs, baseline, doc_labels)
        self._plot_user_claim_doc_heatmap(ax_c, restructured_docs, doc_labels)

        # ── 그래프 하단에 문서 매핑 범례 텍스트 출력 ────────────────
        legend_lines = [
            L(f"{i+1}번 문서: {brief}", f"Doc {i+1}: {brief}")
            for i, brief in enumerate(doc_briefs)
        ]
        legend_text = "\n".join(legend_lines)

        fig.text(
            0.06, 0.22, legend_text,
            fontsize=9.5, va="top", ha="left",
            family=plt.rcParams["font.family"],
            bbox=dict(boxstyle="round,pad=0.6", facecolor="#F7F7F7",
                     edgecolor="#CCCCCC", linewidth=0.8)
        )
        # ────────────────────────────────────────────────────────────

        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"[Phase1Visualizer] 대시보드 저장 완료: {save_path}")
        return save_path

    # ── [A] 문서 단위 유사도 막대그래프 ─────────────────────────
    def _plot_doc_level_bar(self, ax, restructured_docs: list, baseline: dict,
                            doc_labels: list):
        scores = [d["doc_score"] for d in restructured_docs]

        bars = ax.bar(range(len(scores)), scores, color="#4C9BE8",
                      edgecolor="#2C5F8A", linewidth=0.8)

        intra_mean = baseline.get("intra_mean")
        p90        = baseline.get("p90")
        if intra_mean is not None:
            ax.axhline(intra_mean, color="green", ls="--", lw=1.2,
                      label=L(f"평균기준 {intra_mean:.3f}", f"Mean {intra_mean:.3f}"))
        if p90 is not None:
            ax.axhline(p90, color="red", ls=":", lw=1.2,
                      label=L(f"상위10% {p90:.3f}", f"Top10% {p90:.3f}"))

        for bar, sc in zip(bars, scores):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.005,
                    f"{sc:.3f}", ha="center", va="bottom", fontsize=9)

        ax.set_xticks(range(len(doc_labels)))
        ax.set_xticklabels(doc_labels, fontsize=10)
        ax.set_title(L("[A] 문서 단위 유사도 (claims 벡터 기준)",
                      "[A] Document-level Similarity"),
                    fontsize=12, fontweight="bold")
        ax.set_ylabel(L("유사도", "Similarity"))
        ax.legend(fontsize=9, loc="upper right")
        ax.grid(axis="y", ls=":", alpha=0.4)

    # ── [C] 사용자 청구항 × 문서 히트맵 ──────────────────────────
    def _plot_user_claim_doc_heatmap(self, ax, restructured_docs: list,
                                     doc_labels: list):
        """
        사용자 청구항 번호(행) × 문서(열)로 최고 유사도를 히트맵으로 표시.
        시각화 전용으로 보존된 all_claim_pairs(전체 페어)를 사용하여
        Top-5 제한으로 누락되는 청구항이 없도록 한다.
        """
        user_claim_nos = set()
        for d in restructured_docs:
            pairs = d.get("all_claim_pairs", d.get("claim_level_matches", []))
            for m in pairs:
                user_claim_nos.add(m["user_claim_no"])
        user_claim_nos = sorted(user_claim_nos)

        # ── 진단 로그 ────────────────────────────────────────────────
        print(f"\n[진단] 히트맵 — 등장하는 사용자 청구항 번호: {user_claim_nos}")
        for d in restructured_docs:
            pairs = d.get("all_claim_pairs", d.get("claim_level_matches", []))
            source = "all_claim_pairs" if "all_claim_pairs" in d else "claim_level_matches(fallback)"
            matched = sorted({m["user_claim_no"] for m in pairs})
            doc_claim_count = len(set(m["doc_claim_no"] for m in pairs)) if pairs else 0
            print(f"  문서 {d['doc_rank']}위({d['doc_id']}): "
                  f"source={source}  매칭 사용자청구항={matched}  "
                  f"페어수={len(pairs)}  문서청구항수={doc_claim_count}")
        # ────────────────────────────────────────────────────────────
        if not user_claim_nos:
            ax.text(0.5, 0.5, L("데이터 없음", "No data"),
                   ha="center", va="center", transform=ax.transAxes)
            return

        matrix = np.full((len(user_claim_nos), len(restructured_docs)), np.nan)

        for col, d in enumerate(restructured_docs):
            pairs = d.get("all_claim_pairs", d.get("claim_level_matches", []))
            best_per_user_claim = {}
            for m in pairs:
                ucn = m["user_claim_no"]
                if ucn not in best_per_user_claim or m["score"] > best_per_user_claim[ucn]:
                    best_per_user_claim[ucn] = m["score"]
            for row, ucn in enumerate(user_claim_nos):
                if ucn in best_per_user_claim:
                    matrix[row, col] = best_per_user_claim[ucn]

        masked = np.ma.masked_invalid(matrix)
        cmap = plt.cm.get_cmap("YlOrRd").copy()
        cmap.set_bad(color="#F0F0F0")

        im = ax.imshow(masked, cmap=cmap, aspect="auto", vmin=0)
        ax.set_xticks(range(len(doc_labels)))
        ax.set_xticklabels(doc_labels, fontsize=10)
        ax.set_yticks(range(len(user_claim_nos)))
        ax.set_yticklabels(
            [L(f"청구항{n}", f"Claim {n}") for n in user_claim_nos], fontsize=10
        )

        for r in range(len(user_claim_nos)):
            for c in range(len(restructured_docs)):
                val = matrix[r, c]
                if not np.isnan(val):
                    ax.text(c, r, f"{val:.2f}", ha="center", va="center",
                           fontsize=9, color="white" if val > 0.3 else "black")

        ax.set_title(L("[B] 사용자 청구항 × 문서 최고유사도 히트맵",
                      "[B] User Claim x Document Heatmap"),
                    fontsize=12, fontweight="bold")
        cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cbar.ax.set_ylabel(L("유사도", "Similarity"), fontsize=9)

# ════════════════════════════════════════════════════════════════
# Phase 2: 5회 독립 생성 + 클러스터링
# ════════════════════════════════════════════════════════════════
class AgentEnsembleGenerator:
    """
    동일한 단일 프롬프트로 LLM을 NUM_AGENT_RUNS회 독립 호출.
    agent_answer.txt에 5개 결과를 클러스터링 이전 상태로 저장한다
    (요청사항: 클러스터링 이전 저장).
    이후 KorPatBERT로 5개 결과의 독립항을 임베딩하여
    의미론적으로 군집화 → 교집합(반복 등장) / 개별 출현을 분리한다.
    """

    def __init__(self, embedder: KorPatBERTEmbedder, llm_client,
                 output_dir: Path = RUN_OUTPUT_DIR):
        self.embedder   = embedder
        self.llm        = llm_client
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def build_agent_prompt(self, user_input: str, intermediate_summary: str) -> tuple:
        system = "당신은 특허 청구항 작성 전문가입니다."
        prompt = f"""아래 중간 구조화 문서를 기반으로 사용자 아이디어에 대한 특허 독립항을 작성하십시오.

[사용자 아이디어]
{user_input}

[중간 구조화 문서 : 유사 특허 Top-5, 청구항 ver.]
{intermediate_summary}

작성 규칙:
1. 독립항은 1개만 작성하되 보호 범위를 최대한 넓게 잡을 것
2. 위 유사 특허의 청구항과 구성요소 수준에서 명확히 구별될 것
3. "~를 포함하는" 형식으로 구성요소를 나열할 것
4. 종속항은 3개 이내로 작성할 것
5. 각 청구항 뒤에 해당 구성요소가 Top-5 특허와 어떻게 구별되는지 한 줄로 명시할 것

[독립항]
[종속항 1]
[종속항 2]
[종속항 3]
[차별점 근거]
"""
        return system, prompt

    def run_ensemble(self, user_input: str, intermediate_summary: str,
                     n_runs: int = NUM_AGENT_RUNS,
                     save_path: Optional[Path] = None) -> dict:
        """
        반환: {
          "agent_outputs": [str, str, ...]  # n_runs개 원문
          "agent_answer_path": Path,
          "clusters": {...}  # 클러스터링 결과
        }
        """
        system, prompt = self.build_agent_prompt(user_input, intermediate_summary)

        agent_outputs = []
        for i in range(n_runs):
            print(f"[Phase2] Agent {i+1}/{n_runs} 독립 생성 중...")
            output = self.llm.call(system, prompt)
            agent_outputs.append(output)

        # ── agent_answer.txt 저장: 클러스터링 이전 상태 그대로 ──
        save_path = Path(save_path) if save_path else (self.output_dir / "agent_answer.txt")
        self._save_agent_answers(agent_outputs, save_path)

        # ── 클러스터링은 저장 이후에 수행 ──
        clusters = self._cluster_agent_outputs(agent_outputs)

        return {
            "agent_outputs":     agent_outputs,
            "agent_answer_path": save_path,
            "clusters":          clusters,
        }

    def _save_agent_answers(self, agent_outputs: list, save_path: Path):
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "w", encoding="utf-8") as f:
            for i, out in enumerate(agent_outputs, 1):
                f.write(f"{'='*70}\n[Agent {i} 독립 생성 결과]\n{'='*70}\n")
                f.write(out.strip() + "\n\n")
        print(f"[Phase2] agent_answer.txt 저장 완료: {save_path}")

    def _extract_independent_claim_block(self, agent_text: str) -> str:
        """agent 출력에서 [독립항] 블록만 추출."""
        m = re.search(r"\[독립항\](.*?)(?=\[종속항|\Z)", agent_text, re.S)
        return m.group(1).strip() if m else agent_text[:500].strip()

    def _split_into_components(self, indep_text: str) -> list:
        """
        독립항 텍스트를 구성요소 단위로 분해.
        한국어 특허 독립항은 보통 ";" 또는 "," + 동사형 연결("~하는 OOO부;")로
        구성요소가 나열되므로, 이를 기준으로 분리한다.
        분해 실패 시(세미콜론이 없는 경우) 마침표/접속 기준으로 fallback.
        """
        text = indep_text.strip()

        # "~에 있어서," 이후부터가 실제 구성요소 나열 시작
        m = re.search(r"에\s*있어서[,，]?\s*", text)
        body = text[m.end():] if m else text

        # 1차: 세미콜론 기준 분리 (가장 흔한 구성요소 구분자)
        parts = [p.strip() for p in re.split(r"[;；]", body) if p.strip()]

        # 세미콜론이 거의 없으면(구성요소 1~2개로만 잘림) 콤마+"부" 패턴으로 재시도
        if len(parts) <= 2:
            parts = [p.strip() for p in re.split(r"(?<=부)[,，]\s*", body) if p.strip()]

        # 너무 짧은 조각(접속어만 남은 경우) 제거
        parts = [p for p in parts if len(p) >= 15]
        return parts if parts else [body]


    def _clean_for_embedding(self, text: str) -> str:
        """
        임베딩 전 상투적 특허 문구를 제거해 변별력 있는 핵심어 비중을 높인다.
        """
        boilerplate = [
            "인공지능 절전 시스템에 있어서", "을 포함하는 인공지능 절전 시스템",
            "를 포함하는 인공지능 절전 시스템", "인공지능 절전 시스템",
            "을 특징으로 하는", "것을 특징으로 하는", "하는 것을 포함하는",
            "상기", "을 포함하고", "를 포함하고", "포함하는",
        ]
        for b in boilerplate:
            text = text.replace(b, " ")
        return re.sub(r"\s+", " ", text).strip()


    def _cluster_agent_outputs(self, agent_outputs: list) -> dict:
        """
        구성요소 단위 분해 후 클러스터링.
        독립항 전체 문장 대신, 각 구성요소(명사구+역할 설명) 각각을 임베딩하여
        구성요소끼리 매칭한다. 이렇게 해야 "전력 제어부"와 "전력제어부",
        "데이터 수집부"와 "데이터수집부" 같은 동일 개념이 다른 agent에서
        표현만 다르게 등장했을 때 실제로 묶일 수 있다.
        """
        indep_claims = [self._extract_independent_claim_block(t) for t in agent_outputs]

        # 각 agent의 독립항을 구성요소 리스트로 분해
        agent_components = []  # [[comp1, comp2, ...], ...] per agent
        for claim in indep_claims:
            comps = self._split_into_components(claim)
            agent_components.append(comps)

        # 전체 구성요소를 (agent_idx, comp_idx, text) 형태로 펼치기
        flat_components = []
        for a_idx, comps in enumerate(agent_components):
            for c_idx, comp in enumerate(comps):
                flat_components.append((a_idx, c_idx, comp))

        # 구성요소별 임베딩 (cleanup 적용)
        comp_vectors = [
            self.embedder.embed_text(self._clean_for_embedding(text))
            for (_, _, text) in flat_components
        ]

        n = len(flat_components)
        sim_matrix = np.zeros((n, n))
        for i in range(n):
            for j in range(n):
                sim_matrix[i, j] = float(np.dot(comp_vectors[i], comp_vectors[j]))

        # 구성요소 단위 클러스터링 (다른 agent 소속만 매칭 허용)
        COMPONENT_SIM_THRESHOLD = 0.55  # cleanup 후에는 이 값이 다시 유효해짐
        visited = [False] * n
        component_clusters = []
        for i in range(n):
            if visited[i]:
                continue
            group = [i]
            visited[i] = True
            for j in range(n):
                if visited[j]:
                    continue
                same_agent = flat_components[i][0] == flat_components[j][0]
                if not same_agent and sim_matrix[i, j] >= COMPONENT_SIM_THRESHOLD:
                    group.append(j)
                    visited[j] = True
            component_clusters.append(group)

        # 여러 agent에 걸쳐 등장(교집합) vs 한 agent에만 등장(개별)
        intersection_clusters = []
        individual_clusters = []
        for group in component_clusters:
            agents_in_group = {flat_components[idx][0] for idx in group}
            rep_text = flat_components[group[0]][2]
            if len(agents_in_group) >= 2:
                intersection_clusters.append({
                    "agent_indices":       sorted(a + 1 for a in agents_in_group),
                    "representative_text": rep_text,
                    "cluster_size":        len(agents_in_group),
                    "all_texts":           [flat_components[idx][2] for idx in group],
                })
            else:
                individual_clusters.append({
                    "agent_index": flat_components[group[0]][0] + 1,
                    "text":        rep_text,
                })

        # 빈도 내림차순 정렬 (가장 많이 반복된 구성요소가 맨 위로)
        intersection_clusters.sort(key=lambda c: c["cluster_size"], reverse=True)

        return {
            "similarity_matrix":       sim_matrix.tolist(),
            "independent_claim_texts": indep_claims,
            "intersection_clusters":   intersection_clusters,
            "individual_clusters":     individual_clusters,
        }

    def build_cluster_summary_text(self, clusters: dict) -> str:
        lines = ["[Phase 2 클러스터링 결과 — 구성요소 단위 교집합/개별출현 분리]"]
        if clusters["intersection_clusters"]:
            lines.append("\n공통 구성요소 (여러 Agent가 의미적으로 동일한 구성요소를 제시 → 독립항 핵심 골격 후보):")
            for c in clusters["intersection_clusters"]:
                lines.append(
                    f"  - {len(c['agent_indices'])}개 Agent({c['agent_indices']})에서 공통 등장: "
                    f"{c['representative_text'][:150]}"
                )
        if clusters["individual_clusters"]:
            lines.append("\n개별 출현 구성요소 (해당 Agent만 제시 → 종속항/선택적 구성요소 후보):")
            for c in clusters["individual_clusters"][:15]:  # 너무 길어지면 상위만
                lines.append(f"  - Agent{c['agent_index']}만 제시: {c['text'][:150]}")
        return "\n".join(lines)


# ════════════════════════════════════════════════════════════════
# Phase 3: Area Chair 최종 합성기
# ════════════════════════════════════════════════════════════════
class AreaChairSynthesizer:
    """
    중간 요약 + agent_answer 5개 + KorPatBERT 유사도 지형(similarity_landscape)을
    동시에 입력하여 최종 청구항을 합성.
    유사도 지형이 청구 가능한 상한을 calibration하는 역할을 한다.
    """

    SIMILARITY_INTERPRETATION = """유사도 해석 기준은 다음과 같습니다.

* 유사도 0.40 이상: 선행 청구항과 의미적으로 강하게 겹칠 수 있는 위험 구간
* 유사도 0.35 ~ 0.40: 독립항 작성 시 차별화 구성요소가 반드시 필요한 구간
* 유사도 0.30 ~ 0.35: 구성요소 수준의 차별화 검토가 필요한 구간
* 유사도 0.30 미만: 상대적으로 독립항 청구 가능성이 높은 구간

단, 위 기준은 절대적인 법적 판단이 아니라 KorPatBERT 기반 의미 유사도 검증을 위한 참고 기준입니다."""

    def __init__(self, llm_client):
        self.llm = llm_client

    def build_similarity_landscape(self, restructured_docs: list,
                                   domain: str) -> str:
        """
        Phase 1에서 산출된 문서별 점수 + 항별 유사도를
        Phase 3가 그대로 calibration 기준으로 쓸 수 있는 텍스트로 정리.
        """
        baseline = DOMAIN_BASELINES.get(domain, {})
        lines = [
            f"[도메인: {domain} / 통계적 baseline: "
            f"평균={baseline.get('intra_mean',0):.4f}, "
            f"상위10%={baseline.get('p90',0):.4f}]"
        ]
        for d in restructured_docs:
            lines.append(
                f"\n문서 {d['doc_rank']}위 (doc_id={d['doc_id']}, "
                f"문서 전체 유사도={d['doc_score']:.4f}, {d['doc_label']})"
            )
            for m in d["claim_level_matches"]:
                lines.append(
                    f"  - 사용자 청구항{m['user_claim_no']} ↔ "
                    f"해당 문서 청구항{m['doc_claim_no']}: "
                    f"유사도 {m['score']:.4f} ({m['label']})"
                )
        return "\n".join(lines)

    def build_prompt(self, user_input: str, intermediate_summary: str,
                     agent_answer_text: str, similarity_landscape: str) -> tuple:
        system = "당신은 특허 청구항 최종 합성자 역할을 수행합니다."
        prompt = f"""아래의 사용자 원본 아이디어, 중간 구조화 문서 요약, 5개의 독립 생성 결과,
KorPatBERT 유사도 정보를 종합하여 최종 특허 청구항을 작성하십시오.

[사용자 원본 아이디어]
{user_input}

[중간 구조화 문서 요약]
{intermediate_summary}

[Agent 1~5 독립 생성 결과]
{agent_answer_text}

[KorPatBERT 유사도 정보 - 선행기술 지형]
{similarity_landscape}

{self.SIMILARITY_INTERPRETATION}

합성 규칙은 다음과 같습니다.

1. 5개 Agent 결과를 각각 최종안 후보로 선택하지 말고, 구성요소 단위로 분해하십시오.
2. 표현이 다르더라도 의미적으로 동일한 구성요소는 하나의 의미 클러스터로 묶으십시오.
3. 여러 Agent에서 반복적으로 등장한 구성요소는 최종 독립항의 공통 핵심 골격으로 반영하십시오.
4. 반복 출현 빈도가 낮더라도, 선행기술과의 차별성을 만드는 핵심 구성요소라면 독립항에 포함할 수 있습니다.
5. 단순히 청구항 범위를 넓히는 것이 아니라, 선행 청구항과 직접적으로 중복되지 않는 범위 안에서 가능한 넓은 보호 범위를 구성하십시오.
6. 개별 Agent에서만 등장한 구체적 조건, 세부 구현 방식, 선택적 기능은 종속항 후보로 배치하십시오.
7. 유사 특허의 청구항 표현을 그대로 복사하지 말고, 사용자 아이디어의 차별점이 드러나도록 재구성하십시오.
8. 최종 독립항이 기능적 표현에만 머무르는지 자기검증하십시오.
   - 기능만 설명되어 있다면, 이를 수행하는 구조적 구성요소 또는 처리 단계로 재작성하십시오.
9. 최종 청구항 작성 후, KorPatBERT 유사도 기준에서 위험 구간에 해당할 수 있는 표현이 남아 있는지 검토하고, 필요한 경우 차별화 표현을 추가하십시오.

최종 출력 형식은 다음과 같습니다.
[1. 의미 클러스터 분석]
* 공통 핵심 구성요소:
* 선택적 확장 구성요소:
* 선행기술과 겹칠 수 있는 구성요소:
* 차별화 핵심 구성요소:

[2. 최종 독립항]
제1항. ...

[3. 종속항 계층]
제2항. 제1항에 있어서, ...
제3항. 제1항에 있어서, ...

[4. 유사도 기반 청구 근거 요약]
* 어떤 유사도 구간을 기준으로 독립항 범위를 설정했는지 설명하십시오.
* 어떤 구성요소가 선행기술과의 차별성을 만드는지 설명하십시오.
* 어떤 구성요소를 종속항으로 분리했는지 설명하십시오.

[5. 자기검증 결과]
* 기능적 표현 여부:
* 선행 청구항 중복 위험:
* 독립항 범위가 너무 좁거나 넓은지 여부:
* 최종 수정 필요 사항:
"""
        return system, prompt

    def synthesize(self, user_input: str, intermediate_summary: str,
                  agent_answer_text: str, similarity_landscape: str) -> str:
        system, prompt = self.build_prompt(
            user_input, intermediate_summary, agent_answer_text, similarity_landscape
        )
        return self.llm.call(system, prompt)


# ════════════════════════════════════════════════════════════════
# 최종 3-Phase 파이프라인
# ════════════════════════════════════════════════════════════════
class ThreePhaseClaimPipeline:
    """
    Phase 0: 입력 정규화 (자유 형식 → KorPatBERT 형식 / 임베딩 공간 투영용 텍스트)
    Phase 1: claims 검색 top-5 → 문서별 재구조화 + 청구항별 유사도(별도 정렬)
    Phase 2: 동일 프롬프트 5회 독립 생성 → agent_answer.txt 저장 → 클러스터링
    Phase 3: Area Chair 합성 (중간요약 + agent 5개 + 유사도 지형 전체 투입)
    """

    def __init__(self, claims_searcher: ClaimsOnlySearcher,
                 embedder: KorPatBERTEmbedder, llm_client,
                 output_dir: Path = RUN_OUTPUT_DIR):
        self.searcher    = claims_searcher
        self.embedder    = embedder
        self.llm         = llm_client
        self.output_dir  = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.restructurer = IntermediateDocumentRestructurer(claims_searcher, llm_client)
        self.ensemble      = AgentEnsembleGenerator(embedder, llm_client, output_dir)
        self.area_chair    = AreaChairSynthesizer(llm_client)
        self.visualizer     = Phase1Visualizer(output_dir)   
        self.timer          = StageTimer()                

    # ── Phase 0 ──────────────────────────────────────────────
    def phase0_normalize_input(self, raw_input: str, few_shots: list) -> dict:
        """

domain = _verify_domain(raw_input, domain)  # ← 추가: 교차 검증
print(f"[Phase0] 최종 도메인: {domain}")
        사용자 자유 형식 입력을 KorPatBERT 형식(섹션화 JSON)으로 정규화.
        이 단계는 단순 전처리가 아니라, 사용자 입력을 KorPatBERT가 학습한
        임베딩 공간의 좌표계로 투영하기 위한 표현 변환이다.
        이후 모든 phase의 유사도 비교는 이 변환된 표현을 기준으로 수행된다.
        """
        system = "너는 한국어 특허 문서 구조화 및 임베딩 전처리 보조 LLM이다."
        prompt = f"""사용자가 입력한 발명 아이디어 또는 기술 설명을 분석하여, 특허 검색용 JSON으로 변환하라.
출력은 반드시 valid JSON 형식만 사용하고, JSON 바깥에 설명을 쓰지 마라.

작성 시, 제공된 예시 형태를 보고 'JSON으로 변환된 특허'의 양식에 맞춰 작성하라.
제공된 예시는 오로지 형태를 잡기 위한 수단으로만 사용되며, 절대로 내용을 참고하지 마라.

[예시 JSON 파일 형태]
{few_shots}

이 변환의 목적은 KorPatBERT 임베딩 공간에서 검색 가능한 형태로
사용자 입력을 투영하는 것이다. 단순 요약이 아니라, 임베딩 모델이
학습한 특허 문서의 표현 분포(상기, 포함하는, 청구항 N 등의 정형 표현)에
맞춰 사용자 아이디어를 재서술하는 작업이다.

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

4. claims.raw는 반드시 "청구항 1\\n...\\n청구항 2\\n...\\n" 형식으로,
   독립항 1개 이상과 종속항 1개 이상을 명확히 구분하여 작성한다.
   각 항은 "청구항 N" 문구로 시작해야 한다. 매우 중요: "청구항 N" 표기는
   반드시 줄(line)의 맨 앞에서만 사용하고, 항 본문 안에서 선행 청구항을
   인용할 때는 "청구항 N"이 아니라 "제N항에 있어서" 형식을 사용한다.
   (예: 종속항 본문 시작은 "제1항에 있어서," 형태로 작성하고,
   "청구항 1에 있어서,"처럼 쓰지 않는다. 이는 항 분리 로직이
   "청구항 N"을 줄 시작 헤더로만 인식하기 때문이다.)

5. clean 생성 시 다음 정규화 규칙과 공통항 제거 규칙을 반드시 적용한다.

[정규화 규칙]
- 불필요한 반복 공백을 하나의 공백으로 줄인다.
- 줄바꿈이 많을 경우 의미 단위만 유지하고 과도한 줄바꿈은 제거한다.
- 특허 번호, 등록번호, 문헌번호처럼 검색 의미와 직접 관련 없는 식별자는 제거한다.
- "[0001]", "[0010]" 같은 문단 번호는 제거한다.
- claims section에서는 "청구항 1", "제1항에 있어서" 같은 형식적 항 번호 표현을 제거하되,
  핵심 구성요소, 처리 단계, 기술 효과, 데이터 흐름, 장치 구성은 삭제하지 않는다.
- 의미가 불명확한 내용을 임의로 보충하지 않는다.
- 사용자가 제공하지 않은 수치, 장치명, 알고리즘명, 효과를 새로 만들어내지 않는다.

[description 처리 규칙]
background를 제외한 본문 중심(구성요소/동작방식/처리흐름/시스템구조/구현방법) 으로 재구성한다.

[section별 공통항 제거 규칙]
abstract clean: 본 발명은, 일 실시예에 따르면, 에 관한 것이다, 를 제공한다,
를 포함한다, 의 효과가 있다, 적어도 하나 이상의, 하나 이상의, 기 설정된,
미리 설정된, 사용자 단말, 복수의, 상기, 및

claims clean: 상기, 포함하는, 포함하고, 구비하는, 구비하고, 방법으로서,
장치에 있어서, 컴퓨팅 장치에서 수행되는 방법으로서, 하나 이상의 프로세서들,
하나 이상의 프로그램들, 메모리를 구비하고, 제 N 항에 있어서, 삭제, 단계, 수단, 모듈, 복수의

description clean: 본 발명은, 일 실시예에 따르면, 예를 들어, 예컨대, 이하, 상기,
에 관한 것이다, 도면 관련 표현, 기술분야, 배경기술, 선행기술문헌, 발명의 효과,
발명의 내용, 해결하려는 과제, 과제의 해결 수단, 복수의, 하나 이상의

[출력 JSON schema]
{{
  "type": "Ai | BigData | InfoComm | Semiconductor",
  "type_reason": "해당 type으로 분류한 이유",
  "abstract": {{"raw": "...", "clean": "..."}},
  "claims":   {{"raw": "청구항 1\\n...\\n청구항 2\\n제1항에 있어서, ...", "clean": "..."}},
  "description": {{"raw": "...", "clean": "..."}},
  "normalization_log": {{
    "abstract_removed_or_weakened":    [],
    "claims_removed_or_weakened":      [],
    "description_removed_or_weakened": []
  }},
  "missing_information": []
}}

[중요 제한]
- 반드시 JSON만 출력한다.
- 설명 문장, 마크다운, 코드블록을 출력하지 않는다.
- 사용자가 제공하지 않은 구체적 구현 세부사항은 임의로 만들지 않는다.
- 검색 임베딩에 필요한 핵심 명사, 동사, 기술 관계는 유지한다.

사용자 입력:
<
{raw_input}
>>>
"""
        try:
            response = self.llm.call(system, prompt)
            parsed   = robust_json_parse(response)
            if parsed is None:
                raise ValueError("JSON 추출 실패")
            for field in ["type", "abstract", "claims", "description"]:
                if field not in parsed:
                    raise ValueError(f"필드 누락: {field}")
            return parsed
        except Exception as e:
            print(f"[Phase0] 정규화 실패: {e}")
            return {
                "type": "Ai", "type_reason": "기본값(파싱실패)",
                "abstract":    {"raw": raw_input, "clean": raw_input},
                "claims":      {"raw": raw_input, "clean": raw_input},
                "description": {"raw": raw_input, "clean": raw_input},
                "normalization_log": {
                    "abstract_removed_or_weakened":    [],
                    "claims_removed_or_weakened":      [],
                    "description_removed_or_weakened": [],
                },
                "missing_information": ["LLM 처리 실패"],
            }

    # ── 전체 파이프라인 실행 ────────────────────────────────────
    
    def run(self, raw_input: str, top_k_docs: int = 5) -> dict:
        timer = self.timer
        timer.start_pipeline()

        fewshot_path = FEW_SHOT_PATH / "few-shot.json"
        with open(fewshot_path, encoding="utf-8") as f:
            few_shots = [json.load(f)]

        # ── Phase 0 ──────────────────────────────────────────
        send_signal(20000, "사용자 입력 → JSON 변환 시작")

        with timer.stage("Phase 0 (입력 정규화)"):
            print("\n" + "="*60 + "\nPhase 0: 입력 정규화 (임베딩 공간 투영)\n" + "="*60)
            sectioned = self.phase0_normalize_input(raw_input, few_shots)
            domain    = sectioned.get("type", "Ai")
            
            
            domain = verify_domain(raw_input, domain)
            
            print(f"[Phase0] 도메인: {domain}  이유: {sectioned.get('type_reason','')}")


            domain = _verify_domain(raw_input, domain)  # ← 추가: 교차 검증
            print(f"[Phase0] 최종 도메인: {domain}")
            user_claim_items = split_claims_into_items(sectioned["claims"]["raw"])
            print(f"[Phase0] 사용자 청구항 {len(user_claim_items)}개 항으로 분리됨")
            print(f"\n[진단] Phase 0 claims.raw 원문 (앞 800자):")
            print(sectioned["claims"]["raw"][:800])
            print(f"\n[진단] split_claims_into_items 분리 결과:")
            for item in user_claim_items:
                print(f"  청구항{item['claim_no']} "
                      f"(독립={item['is_independent']})  "
                      f"길이={len(item['text'])}자  "
                      f"미리보기: {item['text'][:60]}")

        send_signal(20001, "사용자 입력 → JSON 변환 완료")

        # ── Phase 1 ──────────────────────────────────────────
        send_signal(30000, "유사 특허 탐색 시작")

        with timer.stage("Phase 1 (문서검색+재구조화)"):
            print("\n" + "="*60 + "\nPhase 1: 중간 문서 재구조화\n" + "="*60)

            with timer.sub("  - claims 검색", parent="Phase 1 (문서검색+재구조화)"):
                top5_docs = self.searcher.search(
                    sectioned["claims"]["clean"], domain, k=top_k_docs
                )
            print(f"[Phase1] 문서 단위 top-{top_k_docs} 검색 완료")
            for d in top5_docs:
                print(f"  {d.get('doc_rank','-')} {d['doc_id']}  "
                      f"{d['score']:.4f}  {d['label']}")

            send_signal(30001, "유사 특허 top-5 검색 완료")
            send_signal(30002, "문서별 재구조화 시작")

            restructured_docs = self._restructure_all_timed(
                user_claim_items, top5_docs, domain, timer,
                parent="Phase 1 (문서검색+재구조화)"
            )

            intermediate_summary = self.restructurer.build_intermediate_summary(
                restructured_docs
            )
            inter_path = self.output_dir / "intermediate_summary.txt"
            inter_path.write_text(intermediate_summary, encoding="utf-8")
            print(f"[Phase1] 중간 구조화 문서 저장: {inter_path}")

            send_signal(30003, "문서별 재구조화 완료")

        # ── Phase 1 시각화 ───────────────────────────────────
        with timer.stage("Phase 1 시각화"):
            chart_path = self.visualizer.save_dashboard(restructured_docs, domain)

        # ── Phase 2 ──────────────────────────────────────────
        send_signal(40000, "독립 청구항 5회 생성 시작")

        with timer.stage("Phase 2 (5회 독립생성+클러스터링)"):
            print("\n" + "="*60 + "\nPhase 2: 5회 독립 생성 + 클러스터링\n" + "="*60)
            ensemble_result = self._run_ensemble_timed(
                user_input=raw_input,
                intermediate_summary=intermediate_summary,
                n_runs=NUM_AGENT_RUNS,
                timer=timer,
                parent="Phase 2 (5회 독립생성+클러스터링)",
            )
            cluster_summary_text = self.ensemble.build_cluster_summary_text(
                ensemble_result["clusters"]
            )
            print(f"[Phase2] 클러스터링 완료 "
                  f"(교집합 {len(ensemble_result['clusters']['intersection_clusters'])}개, "
                  f"개별출현 {len(ensemble_result['clusters']['individual_clusters'])}개)")

        send_signal(40001, "독립 청구항 생성 + 클러스터링 완료")

        # ── Phase 3 ──────────────────────────────────────────
        send_signal(50000, "GPT 최종 답변 생성 시작")

        with timer.stage("Phase 3 (Area Chair 합성)"):
            print("\n" + "="*60 + "\nPhase 3: Area Chair 최종 합성\n" + "="*60)
            similarity_landscape = self.area_chair.build_similarity_landscape(
                restructured_docs, domain
            )
            agent_answer_combined = (
                self._read_agent_answer_file(ensemble_result["agent_answer_path"])
                + "\n\n" + cluster_summary_text
            )

            t0 = _time.perf_counter()
            final_claims = self.area_chair.synthesize(
                user_input=raw_input,
                intermediate_summary=intermediate_summary,
                agent_answer_text=agent_answer_combined,
                similarity_landscape=similarity_landscape,
            )
            timer.mark("  - Area Chair LLM 호출",
                      _time.perf_counter() - t0,
                      parent="Phase 3 (Area Chair 합성)")

            final_path = self.output_dir / "final_claims.txt"
            final_path.write_text(final_claims, encoding="utf-8")
            print(f"[Phase3] 최종 청구항 저장: {final_path}")

        send_signal(50001, "GPT 최종 답변 생성 완료")

        timer.print_summary()

        return {
            "sectioned":             sectioned,
            "domain":                domain,
            "top5_docs":             top5_docs,
            "restructured_docs":     restructured_docs,
            "intermediate_summary":  intermediate_summary,
            "phase1_chart_path":     chart_path,
            "agent_outputs":         ensemble_result["agent_outputs"],
            "agent_answer_path":     ensemble_result["agent_answer_path"],
            "clusters":              ensemble_result["clusters"],
            "similarity_landscape":  similarity_landscape,
            "final_claims":          final_claims,
            "timer":                 timer,
        }

    def _restructure_all_timed(self, user_claim_items, top5_docs, domain,
                           timer: StageTimer, parent: str,
                           max_workers: int = 5) -> list:
        """
        문서별 재구조화(청구항 유사도 계산 + LLM 호출)를 병렬로 실행.
        각 문서의 처리는 서로 독립적이므로 ThreadPoolExecutor로 동시 실행한다.
        """
        def process_one_doc(doc_rank: int, doc: dict) -> dict:
            print(f"[Phase1] 문서 {doc_rank}/{len(top5_docs)} 재구조화 시작: {doc['doc_id']}")

            t0 = _time.perf_counter()
            sim_result = self.restructurer._compute_claim_level_similarity(
                user_claim_items, doc, domain
            )
            sim_elapsed = _time.perf_counter() - t0

            claim_level_matches = sim_result["top5"] if isinstance(sim_result, dict) \
                                   else sim_result
            all_claim_pairs = sim_result.get("all_pairs", claim_level_matches) \
                              if isinstance(sim_result, dict) else claim_level_matches

            t0 = _time.perf_counter()
            restructured_text = self.restructurer._llm_restructure(
                doc, claim_level_matches
            )
            llm_elapsed = _time.perf_counter() - t0

            print(f"[Phase1] 문서 {doc_rank}/{len(top5_docs)} 재구조화 완료: "
                  f"{doc['doc_id']}  (LLM {llm_elapsed:.1f}s)")

            return {
                "doc_id":              doc["doc_id"],
                "doc_rank":            doc_rank,
                "doc_score":           doc["score"],
                "doc_label":           doc["label"],
                "restructured_text":   restructured_text,
                "claim_level_matches": claim_level_matches,
                "all_claim_pairs":     all_claim_pairs,
                "_sim_elapsed":        sim_elapsed,
                "_llm_elapsed":        llm_elapsed,
            }

        results_by_rank = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(process_one_doc, rank, doc): rank
                for rank, doc in enumerate(top5_docs, 1)
            }
            for future in as_completed(futures):
                rank = futures[future]
                try:
                    result = future.result()
                    results_by_rank[rank] = result
                except Exception as e:
                    print(f"[Phase1] 문서 {rank} 처리 실패: {e}")
                    # 실패한 문서는 빈 결과로 채움 (전체 파이프라인 중단 방지)
                    doc = top5_docs[rank - 1]
                    results_by_rank[rank] = {
                        "doc_id": doc["doc_id"], "doc_rank": rank,
                        "doc_score": doc["score"], "doc_label": doc["label"],
                        "restructured_text": f"(처리 실패: {e})",
                        "claim_level_matches": [], "all_claim_pairs": [],
                        "_sim_elapsed": 0, "_llm_elapsed": 0,
                    }

        # 원래 순위(rank) 순서로 정렬
        results = [results_by_rank[r] for r in sorted(results_by_rank.keys())]

        # 타이머에 누적 기록 (개별 호출 시간은 보존, 합산은 누적값)
        for r in results:
            timer.mark("  - 청구항 유사도 계산", r.pop("_sim_elapsed"),
                      parent=parent, is_parallel=True)
            timer.mark("  - 문서별 LLM 재구조화", r.pop("_llm_elapsed"),
                      parent=parent, is_parallel=True)

        return results

    # ── Phase 2 ensemble을 개별 시간 측정하며 실행 ────────────────
    def _run_ensemble_timed(self, user_input: str, intermediate_summary: str,
                        n_runs: int, timer: StageTimer, parent: str,
                        max_workers: int = 5) -> dict:
        """
        Agent n_runs회 독립 생성을 병렬로 실행.
        동일 프롬프트를 동시에 여러 번 호출하므로 서로 의존성이 없다.
        """
        system, prompt = self.ensemble.build_agent_prompt(
            user_input, intermediate_summary
        )

        def call_one_agent(idx: int) -> tuple:
            print(f"[Phase2] Agent {idx}/{n_runs} 독립 생성 시작...")
            t0 = _time.perf_counter()
            output = self.llm.call(system, prompt)
            elapsed = _time.perf_counter() - t0
            print(f"[Phase2] Agent {idx}/{n_runs} 완료  ({elapsed:.1f}s)")
            return idx, output, elapsed

        outputs_by_idx = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(call_one_agent, i) for i in range(1, n_runs + 1)]
            for future in as_completed(futures):
                try:
                    idx, output, elapsed = future.result()
                    outputs_by_idx[idx] = output
                    timer.mark("  - Agent별 LLM 호출", elapsed, parent=parent, is_parallel=True)
                except Exception as e:
                    print(f"[Phase2] Agent 호출 실패: {e}")

        # 원래 순서(1~n_runs)대로 정렬 — agent_answer.txt에 일관된 순서로 저장하기 위함
        agent_outputs = [outputs_by_idx[i] for i in sorted(outputs_by_idx.keys())]

        save_path = self.ensemble.output_dir / "agent_answer.txt"
        self.ensemble._save_agent_answers(agent_outputs, save_path)

        t0 = _time.perf_counter()
        clusters = self.ensemble._cluster_agent_outputs(agent_outputs)
        timer.mark("  - 구성요소 클러스터링", _time.perf_counter() - t0, parent=parent)

        return {
            "agent_outputs":     agent_outputs,
            "agent_answer_path": save_path,
            "clusters":          clusters,
        }

    @staticmethod
    def _read_agent_answer_file(path: Path) -> str:
        return Path(path).read_text(encoding="utf-8")


# ════════════════════════════════════════════════════════════════
# PDF 파서
# ════════════════════════════════════════════════════════════════
class PatentPDFParser:
    def __init__(self, min_width=PDF_IMAGE_MIN_WIDTH,
                 min_height=PDF_IMAGE_MIN_HEIGHT, max_images=PDF_MAX_IMAGES):
        self.min_width  = min_width
        self.min_height = min_height
        self.max_images = max_images

    def extract_text(self, pdf_path: str) -> str:
        doc, pages = fitz.open(pdf_path), []
        for n, page in enumerate(doc, 1):
            text = page.get_text("text").strip()
            if is_low_quality_text(text):
                text = ocr_pdf_page(page)
            text = normalize_page_text(text)
            if text and len(text.strip()) >= 200:
                pages.append(f"[페이지 {n}]\n{text}")
        doc.close()
        return "\n\n".join(pages)

    def extract_images(self, pdf_path: str, output_dir: str = None) -> list:
        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="patent_pdf_images_")
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        doc   = fitz.open(pdf_path)
        infos = pdf_pipeline.extract_and_save_images(
            doc, Path(pdf_path).stem, output_dir)
        doc.close()
        return [i["path"] for i in infos if "path" in i][:self.max_images]

    def parse(self, pdf_path: str) -> dict:
        raw_text    = self.extract_text(pdf_path)
        image_paths = self.extract_images(pdf_path)
        sections    = pdf_section.extract_sections(raw_text)
        doc         = fitz.open(pdf_path)
        page_count  = doc.page_count
        doc.close()
        return {"raw_text": raw_text, "sections": sections,
                "image_paths": image_paths, "page_count": page_count}


def parse_pdf_to_prompt_input(pdf_path: str) -> str:
    t0 = _time.perf_counter()

    send_signal(10000, "PDF 텍스트/섹션 추출 시작")
    parser  = PatentPDFParser()
    parsed  = parser.parse(pdf_path)
    t1 = _time.perf_counter()
    print(f"[PDF Timer] 텍스트/섹션 추출(OCR 포함): {t1 - t0:.2f}s")
    send_signal(10001, "PDF 텍스트/섹션 추출 완료")

    secs    = parsed["sections"]
    text    = (f"[PDF 분석 결과]\n발명의 명칭: {secs.get('title','N/A')}\n"
               f"IPC 분류: {secs.get('ipc','N/A')}\n\n"
               f"【요약】\n{secs.get('abstract','없음')}\n\n"
               f"【청구범위】\n{secs.get('claims','없음')}\n\n"
               f"【발명의 설명】\n{secs.get('description','없음')}")

    send_signal(10002, "도면 캡션(LLaVA) 시작")
    captions = []
    for i, p in enumerate(parsed["image_paths"], 1):
        try:
            t_cap0 = _time.perf_counter()
            cap = llava_text(p)
            t_cap1 = _time.perf_counter()
            print(f"[PDF Timer]   도면 {i} LLaVA 캡션: {t_cap1 - t_cap0:.2f}s")
            if cap:
                captions.append(f"[도면 {i}]\n{cap.strip()}")
        except Exception as e:
            print(f"[PDF] 도면 {i} 캡션 실패: {e}")

    t2 = _time.perf_counter()
    print(f"[PDF Timer] 도면 캡션 전체: {t2 - t1:.2f}s  (도면 {len(parsed['image_paths'])}개)")
    send_signal(10003, "도면 캡션(LLaVA) 완료")

    combined = "\n\n".join(captions)
    result = (build_prompt_input_with_image_caption(text, image_caption=combined)
              if combined else text)

    print(f"[PDF Timer] PDF 파싱 전체: {t2 - t0:.2f}s")
    return result
# ════════════════════════════════════════════════════════════════
# 진입점
# ════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="3-Phase 특허 청구항 합성 파이프라인")
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--text", type=str)
    grp.add_argument("--pdf",  type=str)
    ap.add_argument("--output",     default="data/out.txt",
                    help="Phase 3 최종 청구항 텍스트 저장 경로")
    ap.add_argument("--top-k-docs", type=int, default=5,
                    help="Phase 1에서 검색할 유사 문서 수 (기본값 5)")
    ap.add_argument("--n-agents",   type=int, default=NUM_AGENT_RUNS,
                    help="Phase 2 독립 생성 횟수 (기본값 5)")
    args = ap.parse_args()

    NUM_AGENT_RUNS = args.n_agents  # 런타임 오버라이드
    if args.pdf:
        print("[Warmup] LLaVA 모델 사전 로딩 중...")
        t_warmup = _time.perf_counter()
        from llava_text import _load_llava, LlavaCaptionConfig
        _load_llava(LlavaCaptionConfig())
        print(f"[Warmup] LLaVA 모델 로딩 완료 ({_time.perf_counter() - t_warmup:.2f}s)")
    embedder        = KorPatBERTEmbedder()
    claims_searcher = ClaimsOnlySearcher(embedder, NPZ_PATH, JSON_PATH)
    pipeline        = ThreePhaseClaimPipeline(claims_searcher, embedder, LLMClient())

    user_idea = (parse_pdf_to_prompt_input(args.pdf)
                 if args.pdf else args.text)

    result = pipeline.run(user_idea, top_k_docs=args.top_k_docs)

    print("\n" + "="*50 + "\n최종 청구항 (Phase 3 결과)\n" + "="*50)
    print(result["final_claims"])

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(result["final_claims"], encoding="utf-8")
    print(f"\n[저장] {out}")
    print(f"[중간산출물] {pipeline.output_dir}")
    print(f"[Phase1 유사도 차트] {result.get('phase1_chart_path')}")