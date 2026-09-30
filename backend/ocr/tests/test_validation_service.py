from ocr.services.validation_service import (
    build_validation_flags_summary,
    overall_validation_status,
    validate_certificate_fields,
)


def _rule(outcomes, name):
    return next(o for o in outcomes if o.rule_name == name)


def test_passing_shares_rule_carries_no_message():
    # Regression test: a passing rule must not also carry the failure-message
    # text -- that made every successful extraction look like a complaint
    # when inspecting the raw validation_results detail.
    outcomes = validate_certificate_fields({"number_of_shares": "25"})
    rule = _rule(outcomes, "number_of_shares_numeric")
    assert rule.passed is True
    assert rule.message == ""


def test_missing_shares_rule_fails_with_missing_message():
    outcomes = validate_certificate_fields({"number_of_shares": None})
    rule = _rule(outcomes, "number_of_shares_numeric")
    assert rule.passed is False
    assert rule.message == "Number of shares missing"


def test_non_numeric_shares_rule_fails_with_invalid_message():
    outcomes = validate_certificate_fields({"number_of_shares": "twenty-five"})
    rule = _rule(outcomes, "number_of_shares_numeric")
    assert rule.passed is False
    assert rule.message == "Number of shares is not a valid integer"


def test_distinctive_range_matches_shares():
    outcomes = validate_certificate_fields(
        {"number_of_shares": "25", "distinctive_from": "4425", "distinctive_to": "4449"}
    )
    rule = _rule(outcomes, "distinctive_range_matches_shares")
    assert rule.passed is True


def test_distinctive_range_mismatch_flagged():
    outcomes = validate_certificate_fields(
        {"number_of_shares": "25", "distinctive_from": "4425", "distinctive_to": "4500"}
    )
    rule = _rule(outcomes, "distinctive_range_matches_shares")
    assert rule.passed is False


def test_overall_status_and_summary_all_passing():
    outcomes = validate_certificate_fields(
        {
            "number_of_shares": "25",
            "face_value": "10",
            "distinctive_from": "4425",
            "distinctive_to": "4449",
            "date_of_issue": "1967-08-14",
        }
    )
    assert overall_validation_status(outcomes) == "passed"
    assert build_validation_flags_summary(outcomes) == ""


def test_overall_status_failed_when_any_rule_fails():
    outcomes = validate_certificate_fields({"number_of_shares": None})
    assert overall_validation_status(outcomes) == "failed"
    assert "missing" in build_validation_flags_summary(outcomes).lower()
