"""OCR engine abstraction. PaddleOCR is the only extraction engine -- no
LLM, no external API call is ever made from this module. GPU is used when
available and compatible; otherwise it falls back to CPU automatically.
"""

import logging
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

import numpy as np

logger = logging.getLogger("ocr")

try:
    import paddle  # noqa: F401
    from paddleocr import PaddleOCR

    PADDLE_IMPORT_ERROR: Optional[str] = None
except Exception as exc:  # pragma: no cover - exercised only when the optional dep is missing
    paddle = None
    PaddleOCR = None
    PADDLE_IMPORT_ERROR = str(exc)


@dataclass
class OCRLine:
    text: str
    confidence: float
    box: tuple  # (x1, y1, x2, y2) absolute pixel coordinates


@dataclass
class OCRPageResult:
    lines: List[OCRLine]
    image_width: int
    image_height: int


def gpu_diagnostics() -> dict:
    """Best-effort GPU/CUDA detection, independent of whether paddle itself
    is importable, so the system-status endpoint still reports something
    useful on a box where the OCR extras haven't been installed yet."""
    info = {
        "gpu_available": False,
        "gpu_name": None,
        "cuda_available": False,
        "paddle_installed": paddle is not None,
        "paddle_version": None,
        "paddleocr_version": None,
    }

    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            info["gpu_available"] = True
            info["gpu_name"] = result.stdout.strip().splitlines()[0]
    except (FileNotFoundError, subprocess.SubprocessError):
        pass

    if paddle is not None:
        try:
            info["paddle_version"] = paddle.__version__
            compiled_with_cuda = bool(paddle.device.is_compiled_with_cuda())
            info["cuda_available"] = compiled_with_cuda and paddle.device.cuda.device_count() > 0
        except Exception:  # defensive: never let diagnostics crash the API
            pass

    try:
        import paddleocr

        info["paddleocr_version"] = getattr(paddleocr, "__version__", "unknown")
    except Exception:
        pass

    return info


def resolve_device(requested: str) -> str:
    """requested: 'auto' | 'gpu' | 'cpu' -> resolved 'gpu' | 'cpu'."""
    if requested == "cpu":
        return "cpu"
    diagnostics = gpu_diagnostics()
    if requested == "gpu" and not diagnostics["cuda_available"]:
        logger.warning(
            "[OCR] GPU requested but CUDA is not available/compiled in this PaddlePaddle build; falling back to CPU"
        )
        return "cpu"
    if requested == "auto":
        return "gpu" if diagnostics["cuda_available"] else "cpu"
    return requested


class OCRService(ABC):
    @abstractmethod
    def run(self, image_bgr: np.ndarray) -> OCRPageResult:
        ...


class PaddleOCRService(OCRService):
    _instances: dict = {}

    def __init__(self, device: str, lang: str = "en"):
        if PaddleOCR is None:
            raise RuntimeError(
                "PaddleOCR is not installed. Install requirements/ocr-cpu.txt "
                f"(or ocr-gpu.txt on the GPU box). Import error: {PADDLE_IMPORT_ERROR}"
            )
        self.device = device
        self.lang = lang
        self._engine = self._get_or_create_engine(device, lang)

    @classmethod
    def _get_or_create_engine(cls, device: str, lang: str) -> "PaddleOCR":
        key = (device, lang)
        if key not in cls._instances:
            logger.info("[OCR] Initializing PaddleOCR engine (device=%s, lang=%s)", device, lang)
            cls._instances[key] = PaddleOCR(
                use_angle_cls=True,
                lang=lang,
                use_gpu=(device == "gpu"),
                show_log=False,
            )
        return cls._instances[key]

    def run(self, image_bgr: np.ndarray) -> OCRPageResult:
        h, w = image_bgr.shape[:2]
        raw = self._engine.ocr(image_bgr, cls=True)
        lines: List[OCRLine] = []
        page = raw[0] if raw else []
        for entry in page or []:
            box_points, (text, confidence) = entry
            xs = [p[0] for p in box_points]
            ys = [p[1] for p in box_points]
            box = (min(xs), min(ys), max(xs), max(ys))
            lines.append(OCRLine(text=text, confidence=float(confidence), box=box))
        return OCRPageResult(lines=lines, image_width=w, image_height=h)


def get_ocr_service(requested_device: str = "auto", lang: str = "en") -> PaddleOCRService:
    device = resolve_device(requested_device)
    return PaddleOCRService(device=device, lang=lang)
