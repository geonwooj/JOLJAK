import easyocr

print("EasyOCR 초기화 중... (첫 실행 시 모델 다운로드)")
reader = easyocr.Reader(['ko', 'en'], gpu=False)