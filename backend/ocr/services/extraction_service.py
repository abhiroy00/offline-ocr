"""Deterministic, rule-based field extraction from OCR'd page-1 text.

Strategy: keyword-anchored regex over the recognized text lines (robust to
layout drift across decades of certificates), with the document template's
normalized regions used only as a secondary confidence signal -- never as
the sole basis for extraction. Never invents a value: if a field can't be
confidently located, it comes back as value=None, needs_review=True.
"""

import re
from dataclasses import dataclass
from typing import Optional

from ocr.services.paddleocr_service import OCRLine, OCRPageResult
from ocr.templates.share_certificate_v1 import box_in_region, region_for
from ocr.utils.date_parser import normalize_date
from ocr.utils.number_parser import parse_decimal, parse_shares_count
from ocr.utils.text_normalizer import collapse_label, fix_numeric_ocr, normalize_whitespace, strip_noise


@dataclass
class ExtractedField:
    value: Optional[str]
    confidence: float
    source: str  # paddleocr | regex | manual
    page: int
    region: str = ""
    needs_review: bool = False


def _empty(page: int, region: str = "") -> ExtractedField:
    return ExtractedField(value=None, confidence=0.0, source="regex", page=page, region=region, needs_review=True)


_CERT_NO_RE = re.compile(r"CERT(?:IFICATE)?\.?\s*NO\.?\s*[:\-]?\s*(?P<value>[A-Z0-9/\-]{2,20})", re.IGNORECASE)
_HOLDER_PREFIX_RE = re.compile(r"^\s*\d{1,4}\s*/\s*\d{0,4}\s*\|?\s*")
_ISSUE_DATE_RE = re.compile(
    r"(this\s+)?(?P<day>\d{1,2}(?:st|nd|rd|th)?|[A-Za-z]+)\s+day\s+of\s+"
    r"(?P<month>[A-Za-z]+)\.?,?\s*(?P<year>\d{4})",
    re.IGNORECASE,
)
_SHARES_SENTENCE_RE = re.compile(
    r"registered\s+holder.{0,15}?of\s+(?P<shares>[A-Z\s]+?)\s+fully\s+paid\s+"
    r"(?P<type>[A-Za-z()\s]+?)\s+Shares?\s+of\s+Rupees\s+(?P<face>[A-Za-z0-9]+)\s+each",
    re.IGNORECASE,
)

_ORDINAL_WORDS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6,
    "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10, "eleventh": 11,
    "twelfth": 12, "thirteenth": 13, "fourteenth": 14, "fifteenth": 15,
    "sixteenth": 16, "seventeenth": 17, "eighteenth": 18, "nineteenth": 19,
    "twentieth": 20, "thirty-first": 31,
}


def _line_confidence(line: OCRLine) -> float:
    return round(float(line.confidence), 4)


def _region_bonus(line: OCRLine, page: int, field_region: str, image_w: int, image_h: int) -> float:
    region = region_for(page, field_region)
    if region and box_in_region(line.box, image_w, image_h, region):
        return 0.05
    return 0.0


def extract_certificate_no(page: OCRPageResult) -> ExtractedField:
    for line in page.lines:
        match = _CERT_NO_RE.search(line.text)
        if match:
            value = strip_noise(match.group("value"))
            bonus = _region_bonus(line, 1, "certificate_number", page.image_width, page.image_height)
            confidence = min(1.0, _line_confidence(line) + bonus)
            return ExtractedField(
                value=value, confidence=confidence, source="paddleocr", page=1, region="certificate_number"
            )
    return _empty(1, "certificate_number")


_COMPANY_NAME_EXCLUDE_KEYWORDS = ("CERT", "NO OF SHARES", "SHARES", "REGISTERED OFFICE", "AUTHORISED")


def extract_company_name(page: OCRPageResult) -> ExtractedField:
    """The company name is the tallest bounding box (biggest banner text)
    in the upper portion of the page. It is *not* gated on containing
    "LTD"/"LIMITED": decorative certificate fonts routinely OCR that suffix
    away entirely (confirmed against real scans), so a keyword requirement
    would just turn every banner into a needs_review case. Height + position
    is the reliable signal; a LTD/LIMITED/COMPANY match only adds confidence.
    """
    candidates = []
    for line in page.lines:
        label = collapse_label(line.text)
        if not label or len(label) < 4:
            continue
        if any(kw in label for kw in _COMPANY_NAME_EXCLUDE_KEYWORDS):
            continue
        cy = ((line.box[1] + line.box[3]) / 2) / page.image_height
        if cy > 0.32:  # company banner is always in the upper third
            continue
        height = line.box[3] - line.box[1]
        candidates.append((height, line))

    if not candidates:
        return _empty(1, "company_name")

    candidates.sort(key=lambda pair: pair[0], reverse=True)
    _, best_line = candidates[0]
    label = collapse_label(best_line.text)
    value = strip_noise(best_line.text)
    confidence = _line_confidence(best_line)
    if "LTD" in label or "LIMITED" in label or "COMPANY" in label:
        confidence = min(1.0, confidence + 0.1)
    confidence = min(1.0, confidence + _region_bonus(best_line, 1, "company_name", page.image_width, page.image_height))
    needs_review = confidence < 0.5
    return ExtractedField(
        value=value, confidence=confidence, source="paddleocr", page=1, region="company_name",
        needs_review=needs_review,
    )


def extract_holder_name(page: OCRPageResult) -> ExtractedField:
    lines = page.lines
    anchor_idx = None
    for i, line in enumerate(lines):
        if "CERTIFY THAT" in collapse_label(line.text):
            anchor_idx = i
            break
    if anchor_idx is None:
        return _empty(1, "holder_name")

    for j in range(anchor_idx + 1, min(anchor_idx + 4, len(lines))):
        candidate = lines[j]
        label = collapse_label(candidate.text)
        if not label:
            continue
        if "REGISTERED HOLDER" in label or "IS/ARE" in label:
            break
        value = _HOLDER_PREFIX_RE.sub("", candidate.text).strip()
        value = strip_noise(value)
        letter_count = sum(1 for ch in value if ch.isalpha())
        if len(value) >= 3 and letter_count >= 3:
            # A candidate line that's mostly/all digits (e.g. a stray folio
            # serial like "1/21" the prefix regex didn't fully match) is not
            # a name -- keep scanning subsequent lines instead of accepting it.
            bonus = _region_bonus(candidate, 1, "holder_name", page.image_width, page.image_height)
            confidence = min(1.0, _line_confidence(candidate) + bonus)
            return ExtractedField(
                value=value, confidence=confidence, source="paddleocr", page=1, region="holder_name"
            )
    return _empty(1, "holder_name")


def extract_shares_type_and_face_value(page: OCRPageResult) -> dict:
    """Parses the single sentence that carries shares count, share type and
    face value together: '...holder(s) of TWENTY FIVE fully paid Ordinary
    (Equity) Shares of Rupees Ten each...'."""
    full_text = normalize_whitespace(" ".join(line.text for line in page.lines))
    match = _SHARES_SENTENCE_RE.search(full_text)
    if not match:
        return {
            "number_of_shares": _empty(1, "shares_and_face_value"),
            "share_type": _empty(1, "shares_and_face_value"),
            "face_value": _empty(1, "shares_and_face_value"),
        }

    shares_words = match.group("shares")
    type_text = normalize_whitespace(match.group("type"))
    face_words = match.group("face")

    shares_value = parse_shares_count(shares_words)
    face_value = parse_decimal(face_words)
    if face_value is None:
        from ocr.utils.number_parser import words_to_number

        face_value = words_to_number(face_words)

    base_confidence = 0.75  # sentence-level regex match on printed text, not a discrete OCR line box
    return {
        "number_of_shares": ExtractedField(
            value=str(shares_value) if shares_value is not None else None,
            confidence=base_confidence if shares_value is not None else 0.0,
            source="regex",
            page=1,
            region="shares_and_face_value",
            needs_review=shares_value is None,
        ),
        "share_type": ExtractedField(
            value=type_text or None,
            confidence=base_confidence if type_text else 0.0,
            source="regex",
            page=1,
            region="shares_and_face_value",
            needs_review=not bool(type_text),
        ),
        "face_value": ExtractedField(
            value=str(face_value) if face_value is not None else None,
            confidence=base_confidence if face_value is not None else 0.0,
            source="regex",
            page=1,
            region="shares_and_face_value",
            needs_review=face_value is None,
        ),
    }


def extract_issue_date(page: OCRPageResult) -> ExtractedField:
    full_text = normalize_whitespace(" ".join(line.text for line in page.lines))
    match = _ISSUE_DATE_RE.search(full_text)
    if match:
        day_raw = match.group("day").lower()
        day = _ORDINAL_WORDS.get(day_raw)
        if day is None:
            day_digits = re.sub(r"(st|nd|rd|th)$", "", day_raw)
            day = int(day_digits) if day_digits.isdigit() else None
        if day is not None:
            candidate = f"{day} {match.group('month')} {match.group('year')}"
            iso = normalize_date(candidate)
            if iso:
                return ExtractedField(value=iso, confidence=0.7, source="regex", page=1, region="issue_date")

    # Fallback: any recognizable date pattern on the page.
    iso = normalize_date(full_text)
    if iso:
        return ExtractedField(value=iso, confidence=0.5, source="regex", page=1, region="issue_date")
    return _empty(1, "issue_date")


def _looks_numeric(text: str, min_raw_digit_ratio: float = 0.5) -> bool:
    """True only if the RAW (pre-correction) text is already predominantly
    digits. Gates fix_numeric_ocr's letter->digit substitution so it only
    ever cleans up stray misreads inside an already-numeric token (e.g.
    '44O629' -> '440629') -- it must never run on ordinary prose, where it
    would fabricate a number out of the letters (e.g. a date sentence)."""
    chars = [ch for ch in text if not ch.isspace()]
    if not chars:
        return False
    raw_digits = sum(1 for ch in chars if ch.isdigit())
    return (raw_digits / len(chars)) >= min_raw_digit_ratio


def extract_distinctive_numbers(page: OCRPageResult) -> dict:
    region = region_for(1, "distinctive_numbers")
    numeric_lines = []
    for line in page.lines:
        if region and not box_in_region(line.box, page.image_width, page.image_height, region, tolerance=0.02):
            continue
        if not _looks_numeric(line.text):
            continue
        digits = re.sub(r"[^0-9]", "", fix_numeric_ocr(line.text))
        if len(digits) >= 3:
            numeric_lines.append((line.box[1], digits, line))  # sort by vertical position

    numeric_lines.sort(key=lambda t: t[0])

    def make(idx, name):
        if idx >= len(numeric_lines):
            return _empty(1, "distinctive_numbers")
        _, digits, line = numeric_lines[idx]
        confidence = min(1.0, _line_confidence(line) * 0.8)  # handwritten region -> discount confidence
        return ExtractedField(
            value=digits, confidence=confidence, source="paddleocr", page=1, region="distinctive_numbers",
            needs_review=confidence < 0.5,
        )

    return {
        "distinctive_from": make(0, "distinctive_from"),
        "distinctive_to": make(1, "distinctive_to"),
    }


def extract_page1_fields(page: OCRPageResult) -> dict:
    fields = {
        "certificate_no": extract_certificate_no(page),
        "company_name": extract_company_name(page),
        "share_holder_name": extract_holder_name(page),
        "date_of_issue": extract_issue_date(page),
    }
    fields.update(extract_shares_type_and_face_value(page))
    fields.update(extract_distinctive_numbers(page))
    return fields
