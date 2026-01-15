import os
from pdf_processor.pipeline import process_pdf

RAW_DIR = "data/raw_pdf" 

if __name__ == "__main__":
    print(f"처리 디렉토리 확인: {os.path.abspath(RAW_DIR)}")
    
    if not os.path.exists(RAW_DIR):
        print("⚠️ 디렉토리가 존재하지 않습니다! 직접 만들어주세요.")
    else:
        pdf_files = [f for f in os.listdir(RAW_DIR) if f.lower().endswith(".pdf")]
        print(f"발견된 PDF 파일 개수: {len(pdf_files)}")
        
        if not pdf_files:
            print("⚠️ PDF 파일이 없습니다! 폴더에 .pdf 파일을 넣어주세요.")
        else:
            for f in pdf_files:
                full_path = os.path.join(RAW_DIR, f)
                print(f"처리 시작: {f}")
                process_pdf(full_path)
                print(f"완료: {f} → JSON 생성됨")
