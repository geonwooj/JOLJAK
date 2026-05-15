# C:\JOLJAK\ai\pdf_processor\normalize_dispatch.py

import sys
import os

# 현재 파일이 있는 폴더를 강제로 sys.path 최상단에 넣음
sys.path.insert(0, os.path.dirname(__file__))

# 이제 그냥 파일 이름으로 import 가능
import normalize_ver1 as ver1
import normalize_ver2 as ver2

from typing import Literal

VersionType = Literal["ver1", "ver2"]
DEFAULT_VERSION: VersionType = "ver2"


def normalize_text(
    text: str,
    version: VersionType = DEFAULT_VERSION,
    section: str = "general"
) -> str:
    if version == "ver1":
        if section == "abstract":
            return ver1.normalize_abstract(text)
        elif section == "claims":
            return ver1.normalize_claims(text)
        elif section == "description":
            return ver1.normalize_description(text)
        else:
            return ver1.normalize_common(text)

    elif version == "ver2":
        if section == "abstract":
            return ver2.normalize_abstract(text)
        elif section == "claims":
            return ver2.normalize_claims(text)
        elif section == "description":
            return ver2.normalize_description(text)
        else:
            return ver2.normalize_description(text)

    else:
        raise ValueError(f"지원하지 않는 버전: {version}")


def normalize_page_text(text: str, version: VersionType = DEFAULT_VERSION) -> str:
    return normalize_text(text, version=version, section="general")


def normalize_abstract(text: str, version: VersionType = DEFAULT_VERSION) -> str:
    return normalize_text(text, version=version, section="abstract")


def normalize_claims(text: str, version: VersionType = DEFAULT_VERSION) -> str:
    return normalize_text(text, version=version, section="claims")


def normalize_description(text: str, version: VersionType = DEFAULT_VERSION) -> str:
    return normalize_text(text, version=version, section="description")