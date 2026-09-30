"""Row/column extraction for the page-2 'Memorandum of Transfers' table.

The certificates in this corpus have printed column headers but no ruled
grid lines under them, and transfer entries are frequently handwritten,
cramped, and sometimes struck through / superseded by a later entry on the
same certificate. Perfect row segmentation on that input is a genuinely hard
layout problem; rather than pretend otherwise, this module does its best at
row clustering + column bucketing and leans on the confidence system to flag
anything it isn't sure about, per the no-fabrication policy -- it does not
try to silently reconstruct a clean table out of ambiguous handwriting.
"""

from dataclasses import dataclass
from typing import List, Optional

from ocr.services.paddleocr_service import OCRLine, OCRPageResult
from ocr.templates.share_certificate_v1 import PAGE_2_REGIONS
from ocr.utils.date_parser import normalize_date
from ocr.utils.text_normalizer import collapse_label, strip_noise

_HEADER_KEYWORDS = (
    "DATE OF", "TRANSFER NO", "TRANSFEREE", "LEDGER", "FOLIO", "SIGNATURE", "AUTHORIS",
    "MEMORANDUM OF TRANSFERS",
)

_COLUMN_ORDER = ["column_date", "column_transfer_no", "column_transferee", "column_ledger_folio", "column_signature"]
_COLUMN_TO_FIELD = {
    "column_date": "transfer_date",
    "column_transfer_no": "transfer_no",
    "column_transferee": "transferee_name",
    "column_ledger_folio": "ledger_folio_no",
    "column_signature": "authorised_signature",
}

_ROW_Y_GAP = 0.045  # normalized page-height gap that starts a new row
_HEADER_BAND_CY = 0.10  # PaddleOCR frequently splits the header row into
# single-word lines ("Transfer" / "No." on separate boxes), so a keyword
# list alone misses fragments. The header band is a fixed, reliable second
# signal: it's always the first ~10% of the page, well above where any
# handwritten entry starts (confirmed against every sample scan).


@dataclass
class TransferRow:
    row_index: int
    fields: dict  # field_name -> (text, confidence)
    confidence: float
    needs_review: bool


def _is_header_line(line: OCRLine, image_height: int) -> bool:
    label = collapse_label(line.text)
    if any(kw in label for kw in _HEADER_KEYWORDS):
        return True
    cy = ((line.box[1] + line.box[3]) / 2) / image_height
    return cy <= _HEADER_BAND_CY


def _column_for_x(cx: float) -> str:
    best_col, best_overlap = "column_transferee", -1.0
    for col in _COLUMN_ORDER:
        x1, y1, x2, y2 = PAGE_2_REGIONS[col]
        if x1 <= cx <= x2:
            return col
        # distance-based fallback so a token slightly outside its column
        # (common with skewed handwriting) still lands somewhere sane
        overlap = -min(abs(cx - x1), abs(cx - x2))
        if overlap > best_overlap:
            best_overlap = overlap
            best_col = col
    return best_col


def _cluster_rows(lines: List[OCRLine], image_height: int) -> List[List[OCRLine]]:
    ordered = sorted(lines, key=lambda line: (line.box[1] + line.box[3]) / 2)
    rows: List[List[OCRLine]] = []
    current: List[OCRLine] = []
    last_cy: Optional[float] = None
    for line in ordered:
        cy = ((line.box[1] + line.box[3]) / 2) / image_height
        if last_cy is not None and (cy - last_cy) > _ROW_Y_GAP:
            rows.append(current)
            current = []
        current.append(line)
        last_cy = cy
    if current:
        rows.append(current)
    return rows


def extract_transfer_rows(page: OCRPageResult, confidence_threshold: float = 0.70) -> List[TransferRow]:
    data_lines = [line for line in page.lines if not _is_header_line(line, page.image_height)]
    if not data_lines:
        return []

    rows = _cluster_rows(data_lines, page.image_height)

    results: List[TransferRow] = []
    for idx, row_lines in enumerate(rows):
        columns: dict = {col: [] for col in _COLUMN_ORDER}
        for line in row_lines:
            cx = ((line.box[0] + line.box[2]) / 2) / page.image_width
            columns[_column_for_x(cx)].append(line)

        fields = {}
        confidences = []
        for col, field_name in _COLUMN_TO_FIELD.items():
            tokens = sorted(columns[col], key=lambda line: line.box[0])
            text = strip_noise(" ".join(t.text for t in tokens))
            conf = min((t.confidence for t in tokens), default=0.0)
            if tokens:
                confidences.append(conf)
            fields[field_name] = (text or None, conf)

        transferee_text = fields["transferee_name"][0] or ""
        date_text = fields["transfer_date"][0] or ""
        if len(transferee_text) < 2 and not date_text:
            continue  # pure noise fragment, not a plausible transfer entry

        parsed_date = normalize_date(date_text) if date_text else None
        if date_text and parsed_date:
            fields["transfer_date"] = (parsed_date, fields["transfer_date"][1])
        elif date_text and not parsed_date:
            # keep the raw OCR text but flag it -- never silently drop what OCR saw
            confidences.append(0.0)

        row_confidence = round(sum(confidences) / len(confidences), 4) if confidences else 0.0
        needs_review = row_confidence < confidence_threshold or not parsed_date

        results.append(
            TransferRow(row_index=idx, fields=fields, confidence=row_confidence, needs_review=needs_review)
        )

    return results
