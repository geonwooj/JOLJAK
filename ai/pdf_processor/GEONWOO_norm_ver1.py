import re
import unicodedata

# -------------------------
# Common (risk-low)
# -------------------------
_RE_ZERO_WIDTH = re.compile(r'[\u200b\ufeff]')                 # zero-width, BOM
_RE_CTRL_SAFE  = re.compile(r'[\x00-\x08\x0B\x0C\x0E-\x1F]')   # control chars except \t \n \r
_RE_REF_PAREN  = re.compile(r'\(\s*\d{2,6}\s*[a-zA-Z]?\s*\)')  # (100), (110a)  ※ (1) 같은 열거는 남기기 위해 2자리 이상
_RE_WS_NO_NL   = re.compile(r'[ \t\f\v]+')                     # spaces w/o newline
_RE_MULTI_NL   = re.compile(r'\n{3,}')                         # collapse huge blank lines

def normalize_common(text: str) -> str:
    """[공통] 모든 섹션에 적용되는 기초 정규화 (줄바꿈 보존, 약정규화)"""
    if not text:
        return ""

    # 0) 유니코드 정규화 (전각/반각 등)
    text = unicodedata.normalize("NFKC", text)

    # 1) 보이지 않는 유니코드 제거 + 안전한 제어문자 제거 (개행 보존)
    text = _RE_ZERO_WIDTH.sub('', text)
    text = _RE_CTRL_SAFE.sub('', text)

    # 2) 줄바꿈 통일
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    # 3) 도면/부품 참조부호 제거 (보수적)
    text = _RE_REF_PAREN.sub('', text)

    # 4) 같은 줄 내 공백만 정리(개행은 살림)
    text = _RE_WS_NO_NL.sub(' ', text)

    # 5) 과도한 빈 줄만 줄이기
    text = _RE_MULTI_NL.sub('\n\n', text)

    return text.strip()


# -------------------------
# Abstract (risk-low)
# -------------------------
# "본 발명은"만 제거 (뒤 내용을 과하게 먹지 않음)
_RE_ABS_LEAD = re.compile(r'^\s*본\s*발명은\s+', re.IGNORECASE)

# 목적 문구는 "의미어를 보존"하는 방향으로만 약치환
# (너무 공격적으로 잘라내지 않음)
_ABS_PURPOSE_MAP = [
    (re.compile(r'\s*제공하는\s*데\s*그\s*목적이\s*있다\s*\.?\s*$', re.IGNORECASE), ' 제공한다.'),
    (re.compile(r'\s*제공하는\s*것을\s*목적으로\s*한[다당]\s*\.?\s*$', re.IGNORECASE), ' 제공한다.'),
    (re.compile(r'\s*제공하(?:는\s*것)?\s*기\s*위한\s*것이[다당]\s*\.?\s*$', re.IGNORECASE), ' 제공한다.'),
]

def normalize_abstract(text: str) -> str:
    """[요약용] 의미어 손실을 최소화하며 상투적 리드만 약하게 정리"""
    text = normalize_common(text)

    # 리드 구문만 최소 제거
    text = _RE_ABS_LEAD.sub('', text)

    # 종결부 목적 문구를 '의미 유지' 형태로만 축약
    for pat, rep in _ABS_PURPOSE_MAP:
        text = pat.sub(rep, text)

    # 마지막에 한 번 공백만 정리(개행은 이미 common에서 관리)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


# -------------------------
# Claims (risk-low, semicolon-like)
# -------------------------
_RE_CLAIM_DELETE = re.compile(r'(청구항\s*\d+\s*삭제|삭제된\s*청구항\s*\d+)', re.IGNORECASE)

# "청구항 1." "제 1 항:" 같은 헤더 제거
_RE_CLAIM_HEADER = re.compile(r'^\s*(?:청구항|제)\s*\d+\s*(?:항)?\s*[\.\:\)]\s*')

# 종속항 접속부 제거: "청구항 1에 있어서," "제 1항 내지 3 중 어느 한 항에 따른," ...
_RE_DEP_PREFIX = re.compile(
    r'^\s*(?:제\s*\d+\s*항|청구항\s*\d+)'
    r'(?:\s*내지\s*\d+)?\s*(?:중\s*어느\s*한\s*항)?\s*에\s*'
    r'(?:있어서|따른|기재된|의한)\s*,?\s*'
)

# ★과잉 치환 방지★: "특징으로 하는" 전체를 자르지 않고
# "것을 특징으로 하는/하며/한" 같이 템플릿성이 강한 구문만 구분자(;)로 완화
_RE_FEATURE_CUE = re.compile(r'\s*것을\s*특징으로\s*하(?:는|며|여|한)\s*')

# 세미콜론 표준화
_RE_SEMI = re.compile(r'\s*;\s*')
_RE_ENUM_SPACE = re.compile(r'(\d\)|[①②③④⑤⑥⑦⑧⑨⑩])\s*')

def normalize_claims(text: str) -> str:
    """[청구항용] 종속항 접속부 제거 + '것을 특징으로'만 약하게 세미콜론화"""
    text = normalize_common(text)

    # 삭제항 제거
    text = _RE_CLAIM_DELETE.sub(' ', text)

    # claim 단위 분리를 위해 '청구항/제n항' 앞에 개행 삽입(문장 중간 오탐 줄이려면 앞 공백 조건을 둠)
    text = re.sub(r'(?=(?:^|\n)\s*(?:청구항|제)\s*\d+\s*(?:항)?\s*[\.\:\)])', '\n', text)

    blocks = [b.strip() for b in text.split('\n') if b.strip()]
    out_blocks = []

    for b in blocks:
        # 헤더 제거
        b = _RE_CLAIM_HEADER.sub('', b)
        # 종속 접속부 제거(중요)
        b = _RE_DEP_PREFIX.sub('', b)

        # "것을 특징으로 ..."만 약하게 구분자화
        b = _RE_FEATURE_CUE.sub('; ', b)

        # 세미콜론 주변 공백 정리
        b = _RE_SEMI.sub('; ', b)

        # 열거 기호 주변 공백만 정리 (약하게)
        b = _RE_ENUM_SPACE.sub(r' \1 ', b)

        # 너무 과한 공백만 정리
        b = re.sub(r'\s+', ' ', b).strip()
        if b:
            out_blocks.append(b)

    return "\n".join(out_blocks).strip()


# -------------------------
# Description (risk-low)
# -------------------------
_RE_PARA_NO = re.compile(r'(\[\s*\d{4,5}\s*\]|【\s*\d{4,5}\s*】)')  # [0001], 【0012】
_RE_FIG_PHRASE = re.compile(
    r'도\s*\d+(?:[a-zA-Z])?(?:\s*내지\s*도\s*\d+(?:[a-zA-Z])?)?\s*에\s*도시된\s*바와\s*같이,?\s*'
)
_RE_EXAMPLE_CUE = re.compile(r'본\s*발명의\s*(?:일\s*)?실시예(?:들)?(?:에)?\s*따른\s*')

def normalize_description(text: str) -> str:
    """[명세서용] 문단번호/도면 지시어/반복 지시어만 약하게 제거 (의미 손실 최소)"""
    text = normalize_common(text)

    # 문단번호 제거
    text = _RE_PARA_NO.sub('', text)

    # 도면 지시어만 제거(설명 문장은 남김)
    text = _RE_FIG_PHRASE.sub('', text)

    # 반복 지시어 축약
    text = _RE_EXAMPLE_CUE.sub('', text)

    # 공백만 정리(개행은 common에서 이미 안정화)
    text = re.sub(r'\s+', ' ', text).strip()
    return text
