import fitz
import numpy as np
from .reader import reader

def ocr_page(page):
    pix = page.get_pixmap(dpi=200, colorspace=fitz.csGRAY)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
        pix.height, pix.width
    )

    result = reader.readtext(img, detail=0, paragraph=True)
    return "\n".join(result)