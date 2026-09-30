import cv2
import numpy as np
import pytest

from ocr.services.pdf_service import get_page_count, render_pdf_pages
from ocr.services.preprocessing_service import deskew, preprocess_for_ocr


def _text_like_image(angle_degrees: float = 0.0) -> np.ndarray:
    """A synthetic page: white background with black horizontal bars
    standing in for lines of text, optionally rotated."""
    img = np.full((400, 600), 255, dtype=np.uint8)
    for y in range(60, 340, 40):
        cv2.rectangle(img, (60, y), (540, y + 18), 0, thickness=-1)
    if angle_degrees:
        center = (300, 200)
        matrix = cv2.getRotationMatrix2D(center, angle_degrees, 1.0)
        img = cv2.warpAffine(img, matrix, (600, 400), borderValue=255)
    return img


def test_deskew_leaves_axis_aligned_page_untouched():
    img = _text_like_image(0.0)
    _, angle = deskew(img)
    assert angle == 0.0


def test_deskew_corrects_small_rotation():
    img = _text_like_image(6.0)
    _, angle = deskew(img)
    assert 3.0 < abs(angle) < 10.0


def test_deskew_never_applies_implausible_large_rotation():
    # Regression test: cv2.minAreaRect's angle convention differs across
    # OpenCV builds and can otherwise be misread as ~90 degrees on a page
    # that isn't actually rotated (caught via real certificate scans).
    img = _text_like_image(0.0)
    _, angle = deskew(img)
    assert abs(angle) <= 15.0


@pytest.mark.parametrize("filename", ["1605.pdf", "1606.pdf", "1607.pdf", "1608.pdf"])
def test_preprocess_real_certificate_pages_no_bogus_rotation(filename):
    assert get_page_count(f"tests/fixtures/{filename}") == 2
    for page in render_pdf_pages(f"tests/fixtures/{filename}", dpi=200):
        result = preprocess_for_ocr(page.image_bgr)
        for step in result.steps_applied:
            if step.startswith("deskew"):
                degrees = float(step.split("(")[1].rstrip("deg)"))
                assert abs(degrees) <= 15.0
        assert result.processed.shape[0] > 0 and result.processed.shape[1] > 0
