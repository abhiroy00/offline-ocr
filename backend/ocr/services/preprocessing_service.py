"""OpenCV-based adaptive image preprocessing for scanned share certificates.

The pipeline inspects each page (blur, contrast, illumination uniformity) and
only applies the corrections that page actually needs, rather than running
every filter on every image. The original image is always preserved
alongside the processed one so downstream code (and humans reviewing a
flagged record) can fall back to it.
"""

import logging
from dataclasses import dataclass, field
from typing import List

import cv2
import numpy as np

logger = logging.getLogger("ocr")


@dataclass
class PreprocessResult:
    original: np.ndarray
    processed: np.ndarray
    steps_applied: List[str] = field(default_factory=list)


def load_image(path: str) -> np.ndarray:
    image = cv2.imread(path, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Could not read image: {path}")
    return image


def _blur_score(gray: np.ndarray) -> float:
    """Variance of the Laplacian -- lower means blurrier."""
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _contrast_score(gray: np.ndarray) -> float:
    return float(gray.std())


def _illumination_variance(gray: np.ndarray, grid: int = 8) -> float:
    """Std-dev of block-mean brightness across the page. High values mean
    uneven lighting/shadows, which favors adaptive thresholding over a
    single global (Otsu) threshold downstream."""
    h, w = gray.shape[:2]
    bh, bw = max(1, h // grid), max(1, w // grid)
    means = []
    for y in range(0, h, bh):
        for x in range(0, w, bw):
            block = gray[y : y + bh, x : x + bw]
            if block.size:
                means.append(block.mean())
    if len(means) < 2:
        return 0.0
    return float(np.std(means))


MAX_PLAUSIBLE_SKEW_DEGREES = 15.0


def deskew(gray: np.ndarray) -> tuple[np.ndarray, float]:
    """Estimate and correct page rotation using the minimum-area rect of the
    text mass. Returns (rotated_image, angle_degrees). No-op (angle ~ 0) is
    left untouched to avoid introducing interpolation blur on clean scans.

    minAreaRect's angle convention differs between OpenCV builds (old: range
    (-90, 0], new: range [0, 90)), and decorative borders/stamps can throw
    off the estimate entirely. Rather than chase the exact convention, we
    normalize into (-45, 45] and then simply reject anything beyond a
    plausible scan-skew range -- real scans are never actually rotated
    anywhere near 90 degrees, so a reading that extreme means the detector
    locked onto page furniture, not text skew.
    """
    inverted = cv2.bitwise_not(gray)
    _, binary = cv2.threshold(inverted, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    coords = cv2.findNonZero(binary)
    if coords is None or len(coords) < 50:
        return gray, 0.0

    raw_angle = cv2.minAreaRect(coords)[-1]
    angle = raw_angle % 90
    if angle > 45:
        angle -= 90
    angle = -angle

    if abs(angle) < 0.3 or abs(angle) > MAX_PLAUSIBLE_SKEW_DEGREES:
        return gray, 0.0

    (h, w) = gray.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        gray, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )
    return rotated, float(angle)


def remove_borders(gray: np.ndarray, margin_ratio: float = 0.01) -> np.ndarray:
    """Crop a thin uniform margin that often appears as a black scanner
    border around the page."""
    h, w = gray.shape[:2]
    my, mx = int(h * margin_ratio), int(w * margin_ratio)
    if my == 0 and mx == 0:
        return gray
    return gray[my : h - my, mx : w - mx]


def preprocess_for_ocr(image_bgr: np.ndarray) -> PreprocessResult:
    """Adaptive preprocessing: inspect the page, apply only what it needs.

    Returns both the untouched original (BGR) and a processed grayscale
    image tuned for OCR. PaddleOCR's detector is trained on natural/scanned
    text and generally performs *worse* on hard-binarized input, so we do
    NOT binarize the image handed to OCR -- thresholding is only produced as
    a side channel for the table/line-detection step, which needs it.
    """
    steps: List[str] = []
    original = image_bgr.copy()

    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    steps.append("grayscale")

    gray = remove_borders(gray)
    steps.append("border_removal")

    deskewed, angle = deskew(gray)
    if angle:
        gray = deskewed
        steps.append(f"deskew({angle:.2f}deg)")

    blur = _blur_score(gray)
    if blur < 100:
        gray = cv2.GaussianBlur(gray, (0, 0), sigmaX=1.0)
        gray = cv2.addWeighted(gray, 1.5, cv2.GaussianBlur(gray, (0, 0), 3), -0.5, 0)
        steps.append(f"sharpen(blur_score={blur:.0f})")

    if _contrast_score(gray) < 55:
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        gray = clahe.apply(gray)
        steps.append("clahe_contrast")

    denoise_strength = 7
    if blur > 300:  # sharp scan, likely has real noise texture worth cleaning
        gray = cv2.fastNlMeansDenoising(gray, h=denoise_strength)
        steps.append("denoise")

    logger.info("[OCR] Preprocessing steps applied: %s", ", ".join(steps))
    return PreprocessResult(original=original, processed=gray, steps_applied=steps)


def binarize_for_layout_analysis(gray: np.ndarray) -> np.ndarray:
    """Separate, explicit binarization used only by table/line detection,
    which needs a clean black/white mask -- never fed to PaddleOCR itself."""
    illumination_variance = _illumination_variance(gray)
    if illumination_variance > 8:
        return cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 25, 15
        )
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    return binary
