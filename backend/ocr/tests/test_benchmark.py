"""Runs the real pipeline (real PaddleOCR, no mocking) against all 4 sample
certificates and checks cross-document invariants that are true regardless
of per-scan OCR noise -- these are facts about the certificate series
itself (same company, same share count, same date), not guesses about any
one scan's exact OCR output."""

import json

from django.core.management import call_command

from ocr.tests.conftest import fixture_path, requires_paddleocr

EXPECTED_FILES = {"1605.pdf", "1606.pdf", "1607.pdf", "1608.pdf"}


@requires_paddleocr
def test_benchmark_report_invariants(tmp_path):
    call_command(
        "run_benchmark",
        fixtures_dir=fixture_path("."),
        output_dir=str(tmp_path),
        device="cpu",
    )

    report = json.loads((tmp_path / "accuracy_report.json").read_text())
    assert {r["file"] for r in report} == EXPECTED_FILES

    for record in report:
        fields = {name: f["value"] for name, f in record["fields"].items()}

        # Every certificate in this series is for 25 Ordinary (Equity)
        # shares at Rs. 10 face value, issued 14 Aug 1967 -- verified by
        # eye against the scan and true regardless of per-file OCR noise.
        assert fields["number_of_shares"] == "25", record["file"]
        assert fields["share_type"] == "Ordinary (Equity)", record["file"]
        assert fields["face_value"] == "10", record["file"]
        assert fields["date_of_issue"] == "1967-08-14", record["file"]
        assert fields["share_holder_name"] == "KAMANI BROTHERS PRIVATE LTD", record["file"]

        # No-fabrication guard: a distinctive number, when present, must be
        # a short digit string -- never the 15-20 digit soup a letter->digit
        # substitution bug produced on prose text during development.
        for key in ("distinctive_from", "distinctive_to"):
            value = fields[key]
            if value is not None:
                assert value.isdigit() and len(value) <= 10, (record["file"], key, value)

        # certificate_no, when present, must contain this file's own number
        # -- never another certificate's number or unrelated digits.
        cert_no = fields["certificate_no"]
        expected_digits = record["file"].split(".")[0]
        if cert_no is not None:
            assert expected_digits in cert_no, record["file"]
