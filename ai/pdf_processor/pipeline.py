import json
import fitz
import os

import numpy as np

from .quality import is_low_quality_text
from .normalize import normalize_text
from .section import extract_sections
from .claims import split_claims
from .detect import detect_tables, detect_equations
from .ocr_engine import init_ocr_reader, ocr_pdf_page
from paddleocr import PPStructure
structure_engine = None

def extract_and_save_images(doc: fitz.Document, pdf_id: str, output_dir: str = "data/images") -> list[dict]:

    os.makedirs(output_dir, exist_ok=True)
    image_list = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        image_info_list = page.get_images(full=True)  # (xref, smask, width, height, bpc, colorspace, ...)

        for img_index, img in enumerate(image_info_list):
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

                image_list.append({
                    "page": page_num + 1,
                    "filename": img_filename,
                    "width": pix.width,
                    "height": pix.height,
                    "path": img_path,
                })

                pix = None 
            except Exception as e:
                print(f"이미지 추출 실패 (page {page_num+1}, xref {xref}): {e}")

    return image_list

def init_structure_engine():
    global structure_engine
    if structure_engine is None:
        structure_engine = PPStructure(table=True, ocr=True, lang="korean")
    return structure_engine

def analyze_page_structure(page):
    init_structure_engine()
    pix = page.get_pixmap(dpi=200)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
    result = structure_engine(img)
    return result
    
def extract_text_from_page(page):
    text = page.get_text("text")
    if is_low_quality_text(text):
        init_ocr_reader()
        return ocr_pdf_page(page)
    return text


def process_pdf(pdf_path, output_dir="data/processed"):
    doc = fitz.open(pdf_path)
    full_text = ""

    for page in doc:
        page_text = extract_text_from_page(page)
        full_text += normalize_text(page_text) + "\n\n"

    sections = extract_sections(full_text)
    pdf_id = os.path.basename(pdf_path).removesuffix(".pdf")
    sections["id"] = pdf_id
    sections["extracted_images"] = extract_and_save_images(
        doc=doc,
        pdf_id=pdf_id,
        output_dir="data/extracted_figures"   # 원하는 폴더명
    )
    sections["tables_raw"] = detect_tables(full_text)
    sections["equations_detected"] = detect_equations(full_text)
    if sections.get("claims"):
        sections["claims_structured"] = split_claims(sections["claims"])

    os.makedirs(output_dir, exist_ok=True)
    json_path = os.path.join(output_dir, f"{sections['id']}.json")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(sections, f, ensure_ascii=False, indent=4)

    return sections
