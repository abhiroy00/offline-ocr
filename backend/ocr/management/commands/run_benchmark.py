import csv
import json
import os

from django.conf import settings
from django.core.management.base import BaseCommand

from ocr.services.document_classifier import PageType, classify_page
from ocr.services.extraction_service import extract_page1_fields
from ocr.services.paddleocr_service import get_ocr_service
from ocr.services.pdf_service import render_pdf_pages
from ocr.services.preprocessing_service import preprocess_for_ocr
from ocr.services.table_extraction_service import extract_transfer_rows
from ocr.services.validation_service import (
    build_validation_flags_summary,
    overall_validation_status,
    validate_certificate_fields,
)

DEFAULT_FIXTURES = os.path.join(settings.BASE_DIR, "tests", "fixtures")


class Command(BaseCommand):
    help = "Run the OCR pipeline against benchmark certificates and write accuracy_report.json/.csv"

    def add_arguments(self, parser):
        parser.add_argument("--fixtures-dir", default=DEFAULT_FIXTURES)
        parser.add_argument("--output-dir", default=os.path.join(settings.BASE_DIR, "tests", "fixtures"))
        parser.add_argument("--device", default="cpu", choices=["cpu", "gpu", "auto"])

    def handle(self, *args, **options):
        fixtures_dir = os.path.abspath(options["fixtures_dir"])
        output_dir = os.path.abspath(options["output_dir"])
        os.makedirs(output_dir, exist_ok=True)

        pdfs = sorted(f for f in os.listdir(fixtures_dir) if f.lower().endswith(".pdf"))
        if not pdfs:
            self.stdout.write(self.style.ERROR(f"No PDFs found in {fixtures_dir}"))
            return

        ocr_service = get_ocr_service(requested_device=options["device"])
        report = []

        for filename in pdfs:
            path = os.path.join(fixtures_dir, filename)
            self.stdout.write(f"[benchmark] {filename} ...")
            pages = render_pdf_pages(path, dpi=settings.PDF_RENDER_DPI)

            page1_result, page2_result = None, None
            for page in pages:
                processed = preprocess_for_ocr(page.image_bgr)
                result = ocr_service.run(processed.processed)
                page_type = classify_page([line.text for line in result.lines])
                if page_type == PageType.TRANSFER_LEDGER and page2_result is None:
                    page2_result = result
                elif page1_result is None:
                    page1_result = result

            fields = extract_page1_fields(page1_result) if page1_result else {}
            plain_values = {name: f.value for name, f in fields.items()}
            outcomes = validate_certificate_fields(plain_values)
            transfers = extract_transfer_rows(page2_result) if page2_result else []

            record = {
                "file": filename,
                "num_pages": len(pages),
                "fields": {
                    name: {
                        "value": f.value,
                        "confidence": f.confidence,
                        "source": f.source,
                        "needs_review": f.needs_review,
                    }
                    for name, f in fields.items()
                },
                "validation_status": overall_validation_status(outcomes),
                "validation_flags": build_validation_flags_summary(outcomes),
                "transfer_rows": len(transfers),
                "transfer_rows_needing_review": sum(1 for t in transfers if t.needs_review),
            }
            report.append(record)

        json_path = os.path.join(output_dir, "accuracy_report.json")
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)

        csv_path = os.path.join(output_dir, "accuracy_report.csv")
        with open(csv_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["file", "field", "value", "confidence", "needs_review"])
            for record in report:
                for field_name, field in record["fields"].items():
                    writer.writerow([
                        record["file"], field_name, field["value"], field["confidence"], field["needs_review"],
                    ])

        self.stdout.write(self.style.SUCCESS(f"Wrote {json_path} and {csv_path}"))
