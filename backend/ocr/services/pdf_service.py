"""PDF -> page image rendering. Every page is processed independently but
page order/number is always preserved for downstream reassembly."""

from dataclasses import dataclass
from typing import List

import fitz  # PyMuPDF
import numpy as np


@dataclass
class RenderedPage:
    page_number: int  # 1-indexed
    image_bgr: np.ndarray


def get_page_count(pdf_path: str) -> int:
    with fitz.open(pdf_path) as doc:
        return doc.page_count


def render_pdf_pages(pdf_path: str, dpi: int = 300) -> List[RenderedPage]:
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    pages: List[RenderedPage] = []
    with fitz.open(pdf_path) as doc:
        for index in range(doc.page_count):
            pix = doc[index].get_pixmap(matrix=matrix, colorspace=fitz.csRGB)
            image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            if pix.n == 4:
                image = image[:, :, :3]
            image_bgr = image[:, :, ::-1].copy()  # RGB -> BGR for OpenCV
            pages.append(RenderedPage(page_number=index + 1, image_bgr=image_bgr))
    return pages
