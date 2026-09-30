"""Classify a certificate page as the front (share detail) page or the
Memorandum of Transfers page, from already-OCR'd text lines. Deterministic
keyword matching only -- no model inference."""

from enum import Enum
from typing import Iterable

from ocr.utils.text_normalizer import collapse_label

PAGE1_KEYWORDS = (
    "THIS IS TO CERTIFY",
    "CERTIFICATE NO",
    "CERT NO",
    "REGISTERED OFFICE",
    "AUTHORISED CAPITAL",
    "DISTINCTIVE NUMBERS",
    "NO OF SHARES",
)

PAGE2_KEYWORDS = (
    "MEMORANDUM OF TRANSFERS",
    "MEMORANDUM OF TRANSFER",
    "TRANSFEREE",
    "TRANSFEREE'S NAME",
    "LEDGER FOLIO",
    "DATE OF TRANSFER",
)


class PageType(str, Enum):
    CERTIFICATE_FRONT = "certificate_front"
    TRANSFER_LEDGER = "transfer_ledger"
    UNKNOWN = "unknown"


def classify_page(text_lines: Iterable[str]) -> PageType:
    joined = collapse_label(" ".join(text_lines))

    page2_hits = sum(1 for kw in PAGE2_KEYWORDS if kw in joined)
    page1_hits = sum(1 for kw in PAGE1_KEYWORDS if kw in joined)

    if page2_hits and page2_hits >= page1_hits:
        return PageType.TRANSFER_LEDGER
    if page1_hits:
        return PageType.CERTIFICATE_FRONT
    return PageType.UNKNOWN
