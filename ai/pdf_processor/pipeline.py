import json
import fitz
import os
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed

from .quality import is_low_quality_text
from .normalize_dispatch import normalize_page_text
from .section import extract_sections
from .claims import split_claims
from .detect import detect_tables, detect_equations
from .ocr_engine import init_ocr_reader, ocr_pdf_page
from .claims_fallback import fallback_extract_claims


# ============================================================
# Global structure engine (FULL MODE에서만 사용)
# ============================================================

# ============================================================
# 이미지 추출 (FULL MODE 전용)
# ============================================================

def extract_and_save_images(
    doc: fitz.Document,
    pdf_id: str,
    output_dir: str = "data/extracted_figures"
) -> list[dict]:
    """
    페이지별 이미지 추출을 병렬화.
    fitz.Document 자체는 스레드 안전하지 않을 수 있으므로
    페이지 핸들만 미리 추출해 각 스레드가 독립적으로 Pixmap을 생성하도록 한다.
    """
    os.makedirs(output_dir, exist_ok=True)

    def process_page(page_num: int) -> list[dict]:
        page = doc[page_num]
        results = []
        for img_index, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            try:
                pix = fitz.Pixmap(doc, xref)
                if pix.width < 100 or pix.height < 100:
                    continue

                img_filename = f"{pdf_id}_p{page_num+1}_img{img_index+1}.png"
                img_path = os.path.join(output_dir, img_filename)

                if pix.n - pix.alpha > 3:
                    pix = fitz.Pixmap(fitz.csRGB, pix)

                pix.save(img_path)

                results.append({
                    "page": page_num + 1,
                    "filename": img_filename,
                    "width": pix.width,
                    "height": pix.height,
                    "path": img_path,
                })
                pix = None
            except Exception as e:
                print(f"이미지 추출 실패 (page {page_num+1}, xref {xref}): {e}")
        return results

    image_list = []
    # PyMuPDF는 fitz.Document 객체 자체의 페이지 접근이 스레드 락 이슈를 일으킬 수 있어
    # 안전하게 페이지 수만큼만 가벼운 병렬도(4)로 처리
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(process_page, n) for n in range(len(doc))]
        for f in as_completed(futures):
            image_list.extend(f.result())

    return image_list


# ============================================================
# 텍스트 추출 (OCR 최대 1회 제한)
# ============================================================
def extract_text_pages(pages):
    """
    페이지별로 네이티브 텍스트 추출을 먼저 시도하고,
    저품질(=스캔/이미지 페이지)일 때만 OCR을 수행한다.
    OCR은 페이지마다 필요한 경우에 한해 여러 번 수행 가능하도록 수정
    (기존 "최대 1회" 제한이 후반부 이미지 위주 문서에서 텍스트 누락을 유발할 수 있음).
    """
    full_text_parts = []

    for page in pages:
        text = page.get_text("text")

        if is_low_quality_text(text):
            try:
                init_ocr_reader()
                text = ocr_pdf_page(page)
            except Exception as e:
                print(f"OCR 실패: {e}")
                continue

        if text:
            normalized = normalize_page_text(text)
            full_text_parts.append(normalized)

    return "\n\n".join(full_text_parts)


# ============================================================
# FAST MODE : claims 실험용 (🔥 추천)
# ============================================================
def process_pdf_fast(pdf_path):
    """
    ✔ OCR 최대 1회
    ✔ 이미지 / 테이블 / 수식 제거
    ✔ claims 중심 실험용
    ✔ 속도: FULL 대비 5~10배
    """
    doc = fitz.open(pdf_path)
    pdf_id = os.path.basename(pdf_path).removesuffix(".pdf")

    pages = list(doc)
    full_text = extract_text_pages(pages)

    sections = extract_sections(full_text)

    # claims 보정 (핵심)
    if not sections.get("claims") or len(sections["claims"]) < 300:
        fallback_claims = fallback_extract_claims(full_text)
        if fallback_claims:
            sections["claims"] = fallback_claims

    sections["id"] = pdf_id

    if sections.get("claims"):
        sections["claims_structured"] = split_claims(sections["claims"])

    doc.close()
    return sections


# ============================================================
# FULL MODE : 기존 기능 유지 (느리지만 정밀)
# ============================================================
def process_pdf(pdf_path, output_dir="data/processed"):
    """
    ✔ 기존 pipeline 유지
    ✔ OCR 제한 적용
    ✔ FULL 분석용
    """
    doc = fitz.open(pdf_path)
    pdf_id = os.path.basename(pdf_path).removesuffix(".pdf")

    pages = list(doc)
    full_text = extract_text_pages(pages)

    sections = extract_sections(full_text)

    # claims 보정
    if not sections.get("claims") or len(sections["claims"]) < 300:
        fallback_claims = fallback_extract_claims(full_text)
        if fallback_claims:
            sections["claims"] = fallback_claims

    sections["id"] = pdf_id

    # FULL MODE 부가 분석
    sections["extracted_images"] = extract_and_save_images(
        doc=doc,
        pdf_id=pdf_id,
        output_dir="data/extracted_figures"
    )
    sections["tables_raw"] = detect_tables(full_text)
    sections["equations_detected"] = detect_equations(full_text)

    if sections.get("claims"):
        sections["claims_structured"] = split_claims(sections["claims"])

    os.makedirs(output_dir, exist_ok=True)
    json_path = os.path.join(output_dir, f"{pdf_id}.json")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(sections, f, ensure_ascii=False, indent=4)

    doc.close()
    return sections