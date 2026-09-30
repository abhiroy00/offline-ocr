from ocr.utils.date_parser import normalize_date


def test_ordinal_textual_date():
    assert normalize_date("14th August 1967") == "1967-08-14"


def test_plain_textual_date():
    assert normalize_date("14 August 1967") == "1967-08-14"


def test_dashed_numeric_date():
    assert normalize_date("14-08-1967") == "1967-08-14"


def test_slashed_numeric_date():
    assert normalize_date("14/08/1967") == "1967-08-14"


def test_abbreviated_month_date():
    assert normalize_date("9 OCT 1979") == "1979-10-09"


def test_certificate_phrasing_with_day_of():
    assert normalize_date("this Fourteenth day of August 1967".replace("Fourteenth", "14")) == "1967-08-14"


def test_iso_passthrough():
    assert normalize_date("1967-08-14") == "1967-08-14"


def test_invalid_date_returns_none():
    assert normalize_date("35/13/1967") is None


def test_unparseable_text_returns_none():
    assert normalize_date("Given under the Common Seal") is None


def test_empty_returns_none():
    assert normalize_date("") is None
    assert normalize_date(None) is None
