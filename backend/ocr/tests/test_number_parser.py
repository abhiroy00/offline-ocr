from ocr.utils.number_parser import (
    parse_decimal,
    parse_numeric,
    parse_shares_count,
    words_to_number,
)


def test_parse_numeric_extracts_digits():
    assert parse_numeric("25") == 25
    assert parse_numeric("No. of Shares 25") == 25


def test_parse_numeric_returns_none_when_no_digits():
    assert parse_numeric("N/A") is None
    assert parse_numeric("") is None
    assert parse_numeric(None) is None


def test_parse_decimal():
    assert parse_decimal("Rs. 100.00") == 100.0
    assert parse_decimal("10") == 10.0


def test_words_to_number_simple_compound():
    assert words_to_number("TWENTY FIVE") == 25
    assert words_to_number("twenty five") == 25


def test_words_to_number_hundred_and_thousand():
    assert words_to_number("ONE HUNDRED") == 100
    assert words_to_number("ONE THOUSAND") == 1000
    assert words_to_number("TWO HUNDRED AND FIFTY") == 250


def test_words_to_number_tolerates_known_ocr_digit_in_word():
    # "F1VE" is a plausible OCR misread of "FIVE" - single-token dictionary
    # re-check, not a free-form guess.
    assert words_to_number("TWENTY F1VE") == 25


def test_words_to_number_returns_none_for_unrecognized_text():
    assert words_to_number("KAMANI METALS") is None
    assert words_to_number("") is None
    assert words_to_number(None) is None


def test_parse_shares_count_prefers_digits_then_words():
    assert parse_shares_count("25") == 25
    assert parse_shares_count("TWENTY FIVE") == 25
    assert parse_shares_count("") is None
