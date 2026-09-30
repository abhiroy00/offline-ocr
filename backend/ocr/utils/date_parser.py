"""Deterministic date parsing/normalization to YYYY-MM-DD.

Supports the formats called out in the certificate samples:
  "14th August 1967", "14 August 1967", "14-08-1967", "14/08/1967",
  "14 OCT 1979"

Never guesses a date it cannot confidently parse -- returns None instead.
"""

import re
from datetime import date
from typing import Optional

from .text_normalizer import normalize_whitespace

_MONTHS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

_MIN_YEAR = 1850
_MAX_YEAR = 2035

_TEXTUAL_RE = re.compile(
    r"(?P<day>\d{1,2})(?:st|nd|rd|th)?\s+(?:day\s+of\s+)?(?P<month>[A-Za-z]+)\.?,?\s+(?P<year>\d{4})",
    re.IGNORECASE,
)
_NUMERIC_RE = re.compile(r"(?P<day>\d{1,2})[/-](?P<month>\d{1,2})[/-](?P<year>\d{4})")
_ISO_RE = re.compile(r"(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})")


def _to_iso(day: int, month: int, year: int) -> Optional[str]:
    if not (_MIN_YEAR <= year <= _MAX_YEAR):
        return None
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def normalize_date(text: str) -> Optional[str]:
    if not text:
        return None
    text = normalize_whitespace(text)

    match = _ISO_RE.search(text)
    if match:
        return _to_iso(int(match.group("day")), int(match.group("month")), int(match.group("year")))

    match = _TEXTUAL_RE.search(text)
    if match:
        month_key = match.group("month").strip(".").lower()
        month = _MONTHS.get(month_key)
        if month:
            return _to_iso(int(match.group("day")), month, int(match.group("year")))

    match = _NUMERIC_RE.search(text)
    if match:
        day, month, year = int(match.group("day")), int(match.group("month")), int(match.group("year"))
        if month > 12 and day <= 12:
            day, month = month, day
        return _to_iso(day, month, year)

    return None
