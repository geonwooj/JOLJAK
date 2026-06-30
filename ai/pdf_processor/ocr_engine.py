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
            use_angle_cls=True,
            lang='korean',
        )
        print("PaddleOCR 초기화 완료!")
    return ocr_reader


def ocr_pdf_page(page, max_side: int = 1600):
    """
    max_side: OCR 입력 이미지의 긴 변 최대 픽셀 수.
    너무 고해상도로 렌더링하면 OCR 추론 시간이 비선형적으로 늘어나므로
    적절한 상한을 둔다. 특허 도면/텍스트는 1600px 정도면 글자 인식에 충분.
    """
    global ocr_reader
    if ocr_reader is None:
        init_ocr_reader()

    zoom = max_side / max(page.rect.width, page.rect.height)
    zoom = min(zoom, 2.0)  # 너무 작은 페이지를 과도하게 키우지 않도록 상한
    mat = fitz.Matrix(zoom, zoom)

    pix = page.get_pixmap(matrix=mat)
    img_bytes = pix.tobytes("png")
    img = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(img, cv2.IMREAD_COLOR)

    result = ocr_reader.ocr(img, det=True, rec=True, cls=False)

    page_text = ""
    for line in result:
        if line:
            for word_info in line:
                page_text += word_info[1][0] + " "

    return page_text.strip()