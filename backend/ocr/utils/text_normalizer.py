"""Deterministic OCR text-cleanup helpers.

Character-substitution fixes (O<->0, I/l<->1, S<->5, B<->8, ...) are only
ever applied when the caller already knows the expected field type (numeric
vs. alphabetic). We never globally replace characters across free-text like
company or holder names -- that would silently corrupt correct text.
"""

import re
import unicodedata

_WHITESPACE_RE = re.compile(r"\s+")

# Letters OCR commonly confuses for a digit, keyed by the digit they stand in for.
_ALPHA_TO_DIGIT = {
    "O": "0", "Q": "0", "D": "0",
    "I": "1", "L": "1",
    "Z": "2",
    "S": "5",
    "G": "6",
    "T": "7",
    "B": "8",
    "A": "4",
}

# Digits OCR commonly confuses for a letter, used only when reconstructing
# words (e.g. "F1VE" -> "FIVE").
_DIGIT_TO_ALPHA = {
    "0": "O",
    "1": "I",
    "4": "A",
    "5": "S",
    "8": "B",
}


def normalize_whitespace(text: str) -> str:
    if text is None:
        return ""
    text = unicodedata.normalize("NFKC", text)
    return _WHITESPACE_RE.sub(" ", text).strip()


def strip_noise(text: str) -> str:
    """Remove stray punctuation/artifacts that are not part of the value itself."""
    text = normalize_whitespace(text)
    text = text.strip(" .:;,-_'\"|")
    return text


def fix_numeric_ocr(text: str) -> str:
    """Coerce a string that is KNOWN to be numeric by fixing letter look-alikes.

    Only touches characters, does not attempt to interpret the value. Digits
    and separators pass through untouched.
    """
    if not text:
        return text
    out = []
    for ch in text:
        upper = ch.upper()
        if ch.isdigit():
            out.append(ch)
        elif upper in _ALPHA_TO_DIGIT:
            out.append(_ALPHA_TO_DIGIT[upper])
        else:
            out.append(ch)
    return "".join(out)


def fix_word_ocr(word: str) -> str:
    """Coerce a token that is KNOWN to be an alphabetic word by fixing digit
    look-alikes (e.g. "F1VE" -> "FIVE", "0NE" -> "ONE")."""
    if not word:
        return word
    out = []
    for ch in word:
        if ch.isdigit() and ch in _DIGIT_TO_ALPHA:
            out.append(_DIGIT_TO_ALPHA[ch])
        else:
            out.append(ch)
    return "".join(out)


def only_digits(text: str) -> str:
    return re.sub(r"[^0-9]", "", text or "")


def collapse_label(text: str) -> str:
    """Uppercase + collapse whitespace/punctuation for keyword/label matching."""
    text = normalize_whitespace(text).upper()
    text = re.sub(r"[.:]", "", text)
    return text
