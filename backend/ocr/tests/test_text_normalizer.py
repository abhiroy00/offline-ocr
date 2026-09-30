from ocr.utils.text_normalizer import (
    collapse_label,
    fix_numeric_ocr,
    fix_word_ocr,
    normalize_whitespace,
    only_digits,
    strip_noise,
)


def test_normalize_whitespace_collapses_and_trims():
    assert normalize_whitespace("  Kamani   Metals \n & Alloys  ") == "Kamani Metals & Alloys"


def test_normalize_whitespace_handles_none():
    assert normalize_whitespace(None) == ""


def test_strip_noise_removes_trailing_punctuation():
    assert strip_noise(" 1608. ") == "1608"


def test_fix_numeric_ocr_only_touches_letter_lookalikes():
    assert fix_numeric_ocr("O/B/16O8") == "0/8/1608"


def test_fix_numeric_ocr_leaves_pure_digits_untouched():
    assert fix_numeric_ocr("4425") == "4425"


def test_fix_word_ocr_repairs_digit_lookalikes_in_words():
    assert fix_word_ocr("F1VE") == "FIVE"
    assert fix_word_ocr("TWENTY") == "TWENTY"


def test_only_digits_strips_everything_else():
    assert only_digits("O/B/ 1608") == "1608"


def test_collapse_label_for_keyword_matching():
    assert collapse_label(" Cert. No. ") == "CERT NO"
