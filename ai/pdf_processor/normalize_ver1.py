import re
import unicodedata

# -------------------------
# Common (risk-low)
# -------------------------
_RE_ZERO_WIDTH = re.compile(r'[\u200b\ufeff]')          # zero-width, BOM
_RE_CTRL_SAFE  = re.compile(r'[\x00-\x08\x0B\x0C\x0E-\x1F]')   # control chars except \t \n \r
_RE_REF_PAREN  = re.compile(r'\(\s*\d{2,6}\s*[a-zA-Z]?\s*\)')  # (100), (110a)  ※ (1) 같은 열거는 남기기 위해 2자리 이상
_RE_WS_NO_NL   = re.compile(r'[ \t\f\v]+')                    # spaces w/o newline
_RE_MULTI_NL   = re.compile(r'\n{3,}')                        # collapse huge blank lines

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
_RE_ABS_LEAD = re.compile(r'^\s*본\s*발명은\s+', re.IGNORECASE)

_ABS_PURPOSE_MAP = [
    (re.compile(r'\s*제공하는\s*데\s*그\s*목적이\s*있다\s*\.?\s*$', re.IGNORECASE), ' 제공한다.'),
    (re.compile(r'\s*제공하는\s*것을\s*목적으로\s*한[다당]\s*\.?\s*$', re.IGNORECASE), ' 제공한다.'),
    (re.compile(r'\s*제공하(?:는\s*것)?\s*기\s*위한\s*것이[다당]\s*\.?\s*$', re.IGNORECASE), ' 제공한다.'),
]

def normalize_abstract(text: str) -> str:
    """[요약용] 의미어 손실을 최소화하며 상투적 리드만 약하게 정리"""
    text = normalize_common(text)
    text = _RE_ABS_LEAD.sub('', text)
    for pat, rep in _ABS_PURPOSE_MAP:
        text = pat.sub(rep, text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# -------------------------
# Claims (risk-low, semicolon-like)
# -------------------------
_RE_CLAIM_DELETE = re.compile(r'(청구항\s*\d+\s*삭제|삭제된\s*청구항\s*\d+)', re.IGNORECASE)
_RE_CLAIM_HEADER = re.compile(r'^\s*(?:청구항|제)\s*\d+\s*(?:항)?\s*[\.\:\)]\s*')
_RE_DEP_PREFIX = re.compile(
    r'^\s*(?:제\s*\d+\s*항|청구항\s*\d+)'
    r'(?:\s*내지\s*\d+)?\s*(?:중\s*어느\s*한\s*항)?\s*에\s*'
    r'(?:있어서|따른|기재된|의한)\s*,?\s*'
)
_RE_FEATURE_CUE = re.compile(r'\s*것을\s*특징으로\s*하(?:는|며|여|한)\s*')
_RE_SEMI = re.compile(r'\s*;\s*')
_RE_ENUM_SPACE = re.compile(r'(\d\)|[①②③④⑤⑥⑦⑧⑨⑩])\s*')

def normalize_claims(text: str) -> str:
    """[청구항용] 종속항 접속부 제거 + '것을 특징으로'만 약하게 세미콜론화"""
    text = normalize_common(text)
    text = _RE_CLAIM_DELETE.sub(' ', text)
    text = re.sub(r'(?=(?:^|\n)\s*(?:청구항|제)\s*\d+\s*(?:항)?\s*[\.\:\)])', '\n', text)
    blocks = [b.strip() for b in text.split('\n') if b.strip()]
    out_blocks = []
    for b in blocks:
        b = _RE_CLAIM_HEADER.sub('', b)
        b = _RE_DEP_PREFIX.sub('', b)
        b = _RE_FEATURE_CUE.sub('; ', b)
        b = _RE_SEMI.sub('; ', b)
        b = _RE_ENUM_SPACE.sub(r' \1 ', b)
        b = re.sub(r'\s+', ' ', b).strip()
        if b:
            out_blocks.append(b)
    return "\n".join(out_blocks).strip()

# -------------------------
# Description (risk-low)
# -------------------------
_RE_PARA_NO = re.compile(r'(\[\s*\d{4,5}\s*\]|【\s*\d{4,5}\s*】)')
_RE_FIG_PHRASE = re.compile(
    r'도\s*\d+(?:[a-zA-Z])?(?:\s*내지\s*도\s*\d+(?:[a-zA-Z])?)?\s*에\s*도시된\s*바와\s*같이,?\s*'
)
_RE_EXAMPLE_CUE = re.compile(r'본\s*발명의\s*(?:일\s*)?실시예(?:들)?(?:에)?\s*따른\s*')

def normalize_description(text: str) -> str:
    """[명세서용] 문단번호/도면 지시어/반복 지시어만 약하게 제거 (의미 손실 최소)"""
    text = normalize_common(text)
    text = _RE_PARA_NO.sub('', text)
    text = _RE_FIG_PHRASE.sub('', text)
    text = _RE_EXAMPLE_CUE.sub('', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text