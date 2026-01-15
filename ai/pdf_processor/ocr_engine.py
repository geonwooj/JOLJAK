import numpy as np
import fitz
from pathlib import Path

from paddleocr import PaddleOCR
    
ocr_reader = None

def init_ocr_reader():
    global ocr_reader
    if ocr_reader is None:
        print("PaddleOCR 초기화 중... (첫 실행 시 모델 다운로드, 인터넷 필요)")
        ocr_reader = PaddleOCR(
            use_angle_cls=True, 
            lang='korean',
            use_gpu=False            
        )
        print("PaddleOCR 초기화 완료!")
    return ocr_reader

def ocr_pdf_page(page: fitz.Page, dpi: int = 200) -> str:
    
    pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csRGB)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)

    reader = init_ocr_reader()
    result = reader.ocr(img, cls=True)

    if not result or len(result) == 0:
        return ""

    lines = []
    for line in result:
        for word_info in line:
            lines.append(word_info[1][0])
    text = "\n".join(lines)
    text = text.replace("-\n", "").strip()
    text = " ".join(text.split())
    return text.strip()
    
if __name__ == "__main__":
    # 샘플 PDF 페이지 테스트
    doc = fitz.open("sample.pdf")
    page = doc[0]
    text = ocr_pdf_page(page)
    print(text[:500]) 