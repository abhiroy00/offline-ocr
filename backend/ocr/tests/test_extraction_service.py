"""Extraction-logic tests using synthetic OCR lines (no PaddleOCR needed) --
these run in every CI job, unlike the real-OCR integration tests."""

from ocr.services.extraction_service import (
    extract_certificate_no,
    extract_distinctive_numbers,
    extract_holder_name,
    extract_issue_date,
)
from ocr.services.paddleocr_service import OCRLine, OCRPageResult

PAGE_W, PAGE_H = 1000, 1000


def _line(text, x1, y1, x2, y2, confidence=0.95):
    return OCRLine(text=text, confidence=confidence, box=(x1, y1, x2, y2))


def _page(lines):
    return OCRPageResult(lines=lines, image_width=PAGE_W, image_height=PAGE_H)


def test_extract_holder_name_skips_stray_numeric_serial_line():
    # Regression test: a folio/serial fragment ("1/21" OCR'd on its own line
    # as "121") was previously accepted as the holder name outright because
    # the old check only looked at string length. It must be skipped in
    # favor of the real name on the next line.
    page = _page(
        [
            _line("THIS IS TO CERTIFY THAT", 100, 440, 500, 460),
            _line("121", 100, 470, 150, 490),
            _line("KAMANI BROTHERS PRIVATE LTD.", 100, 490, 600, 510),
            _line("is/are the registered holder(s) of TWENTY FIVE", 100, 510, 700, 530),
        ]
    )
    field = extract_holder_name(page)
    assert field.value == "KAMANI BROTHERS PRIVATE LTD"
    assert not field.needs_review


def test_extract_holder_name_returns_empty_when_nothing_looks_like_a_name():
    page = _page(
        [
            _line("THIS IS TO CERTIFY THAT", 100, 440, 500, 460),
            _line("121", 100, 470, 150, 490),
            _line("is/are the registered holder(s) of TWENTY FIVE", 100, 510, 700, 530),
        ]
    )
    field = extract_holder_name(page)
    assert field.value is None
    assert field.needs_review


def test_extract_certificate_no_from_merged_ocr_token():
    page = _page([_line("Cert.No.OB1608", 20, 20, 200, 50)])
    field = extract_certificate_no(page)
    assert field.value == "OB1608"


def test_extract_issue_date_from_day_of_phrase():
    page = _page([_line("this Fourteenth day of August 1967", 100, 650, 500, 670)])
    field = extract_issue_date(page)
    assert field.value == "1967-08-14"


def test_extract_distinctive_numbers_never_fabricates_from_prose():
    # Regression test: fix_numeric_ocr must never run on ordinary sentences
    # swept into the region -- it would turn letters into digit soup (e.g.
    # "this Fourteenth day of August 1967" -> "71507704046571967").
    page = _page(
        [
            _line("Distinctive Numbers", 100, 730, 400, 750),
            _line("From", 100, 755, 200, 775),
            _line("To", 300, 755, 400, 775),
            _line("this Fourteenth day of August 1967", 100, 700, 500, 720),
        ]
    )
    result = extract_distinctive_numbers(page)
    assert result["distinctive_from"].value is None
    assert result["distinctive_to"].value is None
    assert result["distinctive_from"].needs_review
    assert result["distinctive_to"].needs_review


def test_extract_distinctive_numbers_reads_clean_handwritten_digits():
    page = _page(
        [
            _line("Distinctive Numbers", 100, 730, 400, 750, confidence=0.98),
            _line("From", 60, 755, 120, 775, confidence=1.0),
            _line("To", 350, 755, 400, 775, confidence=1.0),
            _line("442605", 60, 758, 190, 778, confidence=0.8),
            _line("442629", 330, 758, 460, 778, confidence=0.8),
        ]
    )
    result = extract_distinctive_numbers(page)
    assert result["distinctive_from"].value == "442605"
    assert result["distinctive_to"].value == "442629"
