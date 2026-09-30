"""Deterministic numeric parsing: digit strings and English number-words.

No LLM, no fuzzy ML guessing. Word matching tolerates a small, explicit set
of OCR digit/letter confusions (see text_normalizer) by re-checking against
a fixed dictionary -- never by inventing values.
"""

import re
from typing import Optional

from .text_normalizer import fix_word_ocr, normalize_whitespace, only_digits

_ONES = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
}

_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}

_SCALES = {
    "hundred": 100,
    "thousand": 1000,
    "lakh": 100_000,
    "lac": 100_000,
    "crore": 10_000_000,
}

_IGNORE_TOKENS = {"and", "only", "rupees", "rs", "rs.", "shares", "share"}

_NUMBER_WORD_RE = re.compile(r"[A-Za-z0-9]+")


def parse_numeric(text: str) -> Optional[int]:
    """Extract a plain integer from a string, fixing letter/digit look-alikes.

    Returns None (never a guess) if no digits are present.
    """
    if not text:
        return None
    digits = only_digits(text)
    if not digits:
        return None
    return int(digits)


def parse_decimal(text: str) -> Optional[float]:
    """Extract a decimal number (e.g. face value like '10.00')."""
    if not text:
        return None
    match = re.search(r"\d+(\.\d+)?", text.replace(",", ""))
    if not match:
        return None
    return float(match.group(0))


def words_to_number(text: str) -> Optional[int]:
    """Convert English number-words (e.g. 'TWENTY FIVE', 'ONE HUNDRED') to int.

    Tolerates common OCR letter/digit confusion inside a token (e.g.
    'F1VE' -> 'FIVE') by re-matching against the fixed dictionary only --
    it never fabricates a value it cannot resolve to a known word.
    """
    if not text:
        return None

    tokens = _NUMBER_WORD_RE.findall(normalize_whitespace(text).lower())
    if not tokens:
        return None

    resolved = []
    for tok in tokens:
        if tok in _IGNORE_TOKENS:
            continue
        candidate = tok
        if candidate not in _ONES and candidate not in _TENS and candidate not in _SCALES:
            candidate = fix_word_ocr(tok.upper()).lower()
        if candidate in _ONES or candidate in _TENS or candidate in _SCALES:
            resolved.append(candidate)
        else:
            # Unknown token -> cannot confidently parse the whole phrase.
            return None

    if not resolved:
        return None

    total = 0
    current = 0
    for word in resolved:
        if word in _ONES:
            current += _ONES[word]
        elif word in _TENS:
            current += _TENS[word]
        elif word == "hundred":
            current = (current or 1) * 100
        else:  # thousand / lakh / crore
            scale = _SCALES[word]
            total += (current or 1) * scale
            current = 0
    return total + current


def parse_shares_count(text: str) -> Optional[int]:
    """Best-effort deterministic parse of a 'number of shares' field that may
    be written as digits ('25') or words ('TWENTY FIVE'). Returns None if
    neither representation can be confidently resolved.
    """
    if not text:
        return None
    numeric = parse_numeric(text) if re.search(r"\d", text) else None
    if numeric is not None:
        return numeric
    return words_to_number(text)
