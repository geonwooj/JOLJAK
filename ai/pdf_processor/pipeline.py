import json
import fitz
import os

from .quality import is_low_quality_text
from .normalize import normalize_text
from .section import extract_sections
from .claims import split_claims
from .detect import detect_tables, detect_equations
from .ocr_engine import init_ocr_reader, ocr_pdf_page
from paddleocr import PPStructure
structure_engine = None

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

    sections["id"] = os.path.basename(pdf_path).removesuffix(".pdf")
    sections["tables_raw"] = detect_tables(full_text)
    sections["equations_detected"] = detect_equations(full_text)
    if sections.get("claims"):
        sections["claims_structured"] = split_claims(sections["claims"])

    os.makedirs(output_dir, exist_ok=True)
    json_path = os.path.join(output_dir, f"{sections['id']}.json")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(sections, f, ensure_ascii=False, indent=4)

    return sections
