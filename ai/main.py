import os
from pipeline.pipeline import process_pdf

RAW_DIR = "data/raw_pdf"

if __name__ == "__main__":
    os.makedirs(RAW_DIR, exist_ok=True)

    for f in os.listdir(RAW_DIR):
        if f.lower().endswith(".pdf"):
            process_pdf(os.path.join(RAW_DIR, f))
