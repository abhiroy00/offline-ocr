"""Deterministic post-extraction validation. Flags suspicious records; never
silently "corrects" them -- a human decides what a failed rule means.
"""

from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from ocr.utils.date_parser import normalize_date


@dataclass
class ValidationOutcome:
    rule_name: str
    passed: bool
    message: str


def _to_int(value) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(str(value))
    except ValueError:
        return None


def validate_certificate_fields(fields: dict) -> List[ValidationOutcome]:
    """fields: plain dict of field_name -> value (already-extracted strings/None)."""
    outcomes: List[ValidationOutcome] = []

    shares = _to_int(fields.get("number_of_shares"))
    outcomes.append(
        ValidationOutcome("number_of_shares_numeric", shares is not None, "Number of shares is not a valid integer")
        if fields.get("number_of_shares") is not None
        else ValidationOutcome("number_of_shares_numeric", False, "Number of shares missing")
    )

    face_value = fields.get("face_value")
    face_value_ok = False
    if face_value not in (None, ""):
        try:
            float(face_value)
            face_value_ok = True
        except ValueError:
            face_value_ok = False
    outcomes.append(
        ValidationOutcome("face_value_numeric", face_value_ok, "" if face_value_ok else "Face value is not numeric")
    )

    dist_from = _to_int(fields.get("distinctive_from"))
    dist_to = _to_int(fields.get("distinctive_to"))
    if dist_from is not None and dist_to is not None:
        outcomes.append(
            ValidationOutcome(
                "distinctive_range_order", dist_from <= dist_to,
                "" if dist_from <= dist_to else "Distinctive 'From' is greater than 'To'",
            )
        )
        if shares is not None:
            expected_shares = dist_to - dist_from + 1
            matches = expected_shares == shares
            outcomes.append(
                ValidationOutcome(
                    "distinctive_range_matches_shares", matches,
                    "" if matches else f"To - From + 1 ({expected_shares}) != number_of_shares ({shares})",
                )
            )
    else:
        outcomes.append(
            ValidationOutcome("distinctive_range_order", False, "Distinctive numbers missing/unreadable")
        )

    issue_date_raw = fields.get("date_of_issue")
    issue_iso = normalize_date(issue_date_raw) if issue_date_raw else None
    outcomes.append(
        ValidationOutcome(
            "date_of_issue_valid", issue_iso is not None,
            "" if issue_iso else "Date of issue missing/unparseable",
        )
    )

    transfer_date_raw = fields.get("present_transfer_date")
    if transfer_date_raw:
        transfer_iso = normalize_date(transfer_date_raw)
        if transfer_iso and issue_iso:
            not_before_issue = date.fromisoformat(transfer_iso) >= date.fromisoformat(issue_iso)
            outcomes.append(
                ValidationOutcome(
                    "transfer_after_issue", not_before_issue,
                    "" if not_before_issue else "Transfer date is earlier than the certificate's issue date",
                )
            )

    return outcomes


def overall_validation_status(outcomes: List[ValidationOutcome]) -> str:
    if not outcomes:
        return "unknown"
    return "passed" if all(o.passed for o in outcomes) else "failed"


def build_validation_flags_summary(outcomes: List[ValidationOutcome]) -> str:
    failures = [o.message for o in outcomes if not o.passed and o.message]
    return "; ".join(failures)
