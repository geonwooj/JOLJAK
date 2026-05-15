import re
import unicodedata

# -------------------------
# 공통 유틸 (방어적 & 저위험, 과삭제 방지)
# -------------------------
_ZERO_WIDTH = r"[\u200B-\u200D\uFEFF]"          # zero-width chars
_CTRL       = r"[\x00-\x08\x0B\x0C\x0E-\x1F]"  # control chars (keep \t \n \r)
_MULTI_WS   = r"[ \t\r\f\v]+"
_MULTI_NL   = r"\n{3,}"

# [최종] 참조부호/부품번호: (100), (110a), (100,110), (100-110), [100a~110b] 등만 제거
#       (1), (2-5) 같은 "단계/열거"는 남기도록 2자리 이상 or 문자 포함 조건을 추가
_REF_NUM_PAREN = re.compile(
    r"[\(\[\{]\s*(?=[^)\]\}]*?(?:\d{2,}|[a-zA-Z]))"
    r"\d{1,6}[a-zA-Z]?(?:\s*(?:,|~|-)\s*\d{1,6}[a-zA-Z]?)*\s*[\)\]\}]"
)

# 문서 내 문단 번호: [0001], 【0001】, (0001) 등
_PARA_NO = re.compile(r"(?:\[\s*\d{3,5}\s*\]|【\s*\d{3,5}\s*】|\(\s*\d{3,5}\s*\))")

# 짧아도 "기술 토큰"이면 살리는 예외(필요시 추가)
_TECH_TOKEN_RE = re.compile(
    r"\b(?:AI|GAN|SIFT|CNN|RNN|LSTM|GRU|Transformer|BERT|GPU|TPU|CPU|NPU|DSP|FPGA|ASIC|SoC|SRAM|DRAM)\b",
    re.IGNORECASE
)

def _base_normalize(text: str) -> str:
    """모든 필드에 공통 적용하는 '저위험' 정규화."""
    if not text:
        return ""

    # 1) Unicode 정규화 (전각/반각 통일)
    text = unicodedata.normalize("NFKC", text)

    # 2) 제어/제로폭 문자 제거
    text = re.sub(_ZERO_WIDTH, "", text)
    text = re.sub(_CTRL, "", text)

    # 3) 줄바꿈 통일
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # 4) 참조부호 제거(과삭제 방지 적용)
    text = _REF_NUM_PAREN.sub("", text)

    # 5) 공백 정리 (개행은 유지)
    text = re.sub(_MULTI_WS, " ", text)
    text = re.sub(_MULTI_NL, "\n\n", text)

    return text.strip()


def _content_score_weak(s: str) -> int:
    """
    '너무 약한 조각(파싱 찌꺼기)'을 버리기 위한 가벼운 내용 점수.
    - 한글/영문 글자 수 + (기술에서 자주 쓰는) 하이픈/슬래시 포함 정도만 반영
    """
    if not s:
        return 0
    letters = len(re.findall(r"[가-힣A-Za-z]", s))
    tech_punc = len(re.findall(r"[-_/]", s))
    return letters + tech_punc


# -------------------------
# Abstract 전용 (약정규화)
# -------------------------
_ABS_HEADERS = re.compile(r"^\s*(요약|ABSTRACT)\s*[:：]?\s*", re.IGNORECASE)

def normalize_abstract(text: str) -> str:
    t = _base_normalize(text)

    # 헤더 및 문단번호 제거
    t = _ABS_HEADERS.sub("", t)
    t = _PARA_NO.sub("", t)

    # 문장 단위로 분리하여 "파편"만 버림(너무 공격적 제거 금지)
    parts = re.split(r"(?<=[\.\?\!]|다\.)\s+|\n+", t)
    kept = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # 아주 짧은 문장도 대부분 보존 (파싱 찌꺼기만 컷)
        if _content_score_weak(p) >= 5 or _TECH_TOKEN_RE.search(p):
            kept.append(p)

    out = " ".join(kept) if kept else t
    out = re.sub(_MULTI_WS, " ", out).strip()
    return out


# -------------------------
# Claims 전용 (핵심: 세미콜론 중심 + 종속항 접속부 제거 + 과삭제 방지)
# -------------------------
_CLAIM_DELETE = re.compile(r"(청구항\s*\d+\s*삭제|삭제된\s*청구항\s*\d+)", re.IGNORECASE)

# 청구항 의존 접속부(템플릿) 제거
_DEP_PREFIX = re.compile(
    r"^\s*(?:청구항|제)\s*\d+\s*(?:항)?\s*"
    r"(?:내지\s*\d+\s*(?:항)?)?\s*(?:중\s*어느\s*한\s*항)?\s*에\s*"
    r"(?:있어서|따른|기재된|의한)\s*,?\s*"
)

# 흔한 claim 번호/머리말 제거
_CLAIM_NO = re.compile(r"^\s*(?:청구항|제)\s*\d+\s*(?:항)?\s*[\.\:\)]\s*")

# 세미콜론/열거 구분자 통일
_SEMI_EQUIV = [
    (re.compile(r"[；]"), ";"),
    (re.compile(r"\s*;\s*"), "; "),
]

# 세미콜론 조각 앞의 약한 템플릿 토큰 정리
_LEAD_WEAK = re.compile(r"^\s*(상기|또는|및|그|해당|더욱)\s+")

def normalize_claims(text: str) -> str:
    t = _base_normalize(text)

    t = _CLAIM_DELETE.sub(" ", t)
    t = _PARA_NO.sub(" ", t)

    # [최종] 줄이 합쳐지는 파싱 케이스 대비: "청구항 n:" / "제 n 항:" 앞에 강제 개행 삽입
    t = re.sub(r"(?=(?:청구항|제)\s*\d+\s*(?:항)?\s*[\.\:\)])", "\n", t)

    for pat, rep in _SEMI_EQUIV:
        t = pat.sub(rep, t)

    lines = [ln.strip() for ln in re.split(r"\n+", t) if ln.strip()]
    normalized_claims = []

    for ln in lines:
        ln = _CLAIM_NO.sub("", ln)
        ln = _DEP_PREFIX.sub("", ln)

        chunks = [c.strip() for c in ln.split(";") if c.strip()]
        kept_chunks = []
        for c in chunks:
            c = _LEAD_WEAK.sub("", c).strip()

            # [최종] 너무 짧은 조각은 원칙적으로 컷하되, 기술 토큰/의미어는 예외로 살림
            score = _content_score_weak(c)
            if score >= 8 or _TECH_TOKEN_RE.search(c):
                kept_chunks.append(c)

        if kept_chunks:
            normalized_claims.append("; ".join(kept_chunks))
        else:
            # 세미콜론 분해가 불능이면 원문(약정규화만) 유지
            normalized_claims.append(ln.strip())

    out = "\n".join([re.sub(_MULTI_WS, " ", x).strip() for x in normalized_claims if x.strip()])
    return out.strip()


# -------------------------
# Description 전용 (약정규화)
# -------------------------
_FIG_SECTION = re.compile(r"(도면의\s*간단한\s*설명|도면\s*간단\s*설명|부호의\s*설명)\s*[:：]?", re.IGNORECASE)
_FIG_LINE = re.compile(r"^\s*도\s*\d+(?:[a-zA-Z])?\s*[은는]\s*.*$", re.MULTILINE)
_SYMBOL_LINE = re.compile(r"^\s*\d{2,6}[a-zA-Z]?\s*[:：\-]\s*.*$", re.MULTILINE)

def normalize_description(text: str) -> str:
    t = _base_normalize(text)

    t = _PARA_NO.sub("", t)

    # "도면의 간단한 설명/부호의 설명" 섹션 헤더만 제거 (내용은 최대한 유지)
    t = _FIG_SECTION.sub(" ", t)

    # 도면 캡션 라인 / 부호 리스트 라인 제거(반복 노이즈가 크기 때문)
    t = _FIG_LINE.sub(" ", t)
    t = _SYMBOL_LINE.sub(" ", t)

    t = re.sub(_MULTI_WS, " ", t)
    t = re.sub(_MULTI_NL, "\n\n", t).strip()
    return t
