import numpy as np
import fitz
from pathlib import Path
import cv2

from paddleocr import PaddleOCR
    
ocr_reader = None

def init_ocr_reader():
    global ocr_reader
    if ocr_reader is None:
        print("PaddleOCR 초기화 중... (첫 실행 시 모델 다운로드, 인터넷 필요)")
        ocr_reader = PaddleOCR(
            use_angle_cls=True,    # ← 회전 분류기 활성화 (이게 cls 역할)
            lang='korean',
            # use_gpu=False       # ← 삭제 또는 주석
            # device='cpu'        # 필요 시 명시
        )
        print("PaddleOCR 초기화 완료!")
    return ocr_reader

def ocr_pdf_page(page):
    global ocr_reader
    if ocr_reader is None:
        init_ocr_reader()

    # 페이지 이미지를 numpy 배열로 변환 (fitz 페이지 → PIL → numpy)
    pix = page.get_pixmap()
    img_bytes = pix.tobytes("png")
    img = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(img, cv2.IMREAD_COLOR)

    # OCR 실행 – cls 인자 제거 (초기화 시 use_angle_cls=True로 이미 설정됨)
    result = ocr_reader.ocr(img, det=True, rec=True, cls=False)  # cls=False 또는 생략

    # 결과 처리 (기존 코드 그대로)
    page_text = ""
    for line in result:
        if line:
            for word_info in line:
                page_text += word_info[1][0] + " "  # 텍스트만 추출

    return page_text.strip()
    
if __name__ == "__main__":
    # 샘플 PDF 페이지 테스트
    doc = fitz.open("sample.pdf")
    page = doc[0]
    text = ocr_pdf_page(page)
    print(text[:500]) 