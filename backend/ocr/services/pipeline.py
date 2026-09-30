"""End-to-end per-document pipeline: render -> preprocess -> OCR -> classify
-> extract -> validate -> persist. This is the module Celery tasks call; it
is the only place that touches both the pure services above and the Django
models, keeping the services themselves framework-free and unit-testable.
"""

import logging
import os
from typing import Optional

from django.conf import settings
from django.utils import timezone

from ocr.models import Certificate, CertificateField, Document, TransferRecord, ValidationResult
from ocr.services.document_classifier import PageType, classify_page
from ocr.services.extraction_service import extract_page1_fields
from ocr.services.paddleocr_service import OCRPageResult, get_ocr_service
from ocr.services.pdf_service import render_pdf_pages
from ocr.services.preprocessing_service import load_image, preprocess_for_ocr
from ocr.services.table_extraction_service import extract_transfer_rows
from ocr.services.validation_service import (
    build_validation_flags_summary,
    overall_validation_status,
    validate_certificate_fields,
)

logger = logging.getLogger("ocr")

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".webp", ".bmp"}


class PipelineError(Exception):
    def __init__(self, stage: str, error_type: str, message: str):
        super().__init__(message)
        self.stage = stage
        self.error_type = error_type
        self.message = message


def _pages_for_document(path: str, ext: str, dpi: int):
    if ext == ".pdf":
        try:
            return [(p.page_number, p.image_bgr) for p in render_pdf_pages(path, dpi=dpi)]
        except Exception as exc:  # noqa: BLE001
            raise PipelineError("PDF_CONVERSION", type(exc).__name__, str(exc)) from exc
    try:
        return [(1, load_image(path))]
    except Exception as exc:  # noqa: BLE001
        raise PipelineError("PDF_CONVERSION", type(exc).__name__, str(exc)) from exc


def _field_confidence_average(field_values: dict) -> float:
    confidences = [f.confidence for f in field_values.values() if f is not None]
    return round(sum(confidences) / len(confidences), 4) if confidences else 0.0


def process_document(document_id: int, engine_device: str = "auto") -> None:
    document = Document.objects.get(pk=document_id)
    document.status = Document.Status.PROCESSING
    document.save(update_fields=["status"])
    logger.info("[OCR] Document %s: starting (%s)", document.id, document.original_filename)

    try:
        path = document.file.path
        ext = os.path.splitext(document.original_filename)[1].lower()
        pages = _pages_for_document(path, ext, settings.PDF_RENDER_DPI)
        document.num_pages = len(pages)
        document.save(update_fields=["num_pages"])

        try:
            ocr_service = get_ocr_service(requested_device=engine_device, lang=settings.OCR_LANG)
        except Exception as exc:  # noqa: BLE001
            raise PipelineError("OCR", type(exc).__name__, str(exc)) from exc

        page1_result: Optional[OCRPageResult] = None
        page1_number = None
        page2_result: Optional[OCRPageResult] = None

        for page_number, image_bgr in pages:
            try:
                processed = preprocess_for_ocr(image_bgr)
            except Exception as exc:  # noqa: BLE001
                raise PipelineError("PREPROCESSING", type(exc).__name__, str(exc)) from exc

            try:
                result = ocr_service.run(processed.processed)
            except Exception as exc:  # noqa: BLE001
                raise PipelineError("OCR", type(exc).__name__, str(exc)) from exc

            page_type = classify_page([line.text for line in result.lines])
            logger.info("[OCR] Document %s page %s classified as %s", document.id, page_number, page_type.value)

            if page_type == PageType.TRANSFER_LEDGER and page2_result is None:
                page2_result = result
            elif page1_result is None:
                page1_result, page1_number = result, page_number

        try:
            _persist_results(document, page1_result, page1_number, page2_result)
        except Exception as exc:  # noqa: BLE001
            raise PipelineError("DATABASE", type(exc).__name__, str(exc)) from exc

        document.status = Document.Status.DONE
        document.processed_at = timezone.now()
        document.save(update_fields=["status", "processed_at"])
        logger.info("[OCR] Document %s: SUCCESS", document.id)

    except PipelineError as exc:
        document.status = Document.Status.FAILED
        document.error_stage = exc.stage
        document.error_type = exc.error_type
        document.error_message = exc.message
        document.processed_at = timezone.now()
        document.save(update_fields=["status", "error_stage", "error_type", "error_message", "processed_at"])
        logger.warning("[OCR] Document %s: FAILED at %s (%s)", document.id, exc.stage, exc.error_type)
    except Exception as exc:  # noqa: BLE001 - last-resort catch so one bad file never kills a batch
        document.status = Document.Status.FAILED
        document.error_stage = Document.Stage.EXTRACTION
        document.error_type = type(exc).__name__
        document.error_message = str(exc)
        document.processed_at = timezone.now()
        document.save(update_fields=["status", "error_stage", "error_type", "error_message", "processed_at"])
        logger.error("[OCR] Document %s: UNEXPECTED FAILURE (%s)", document.id, type(exc).__name__)


def _persist_results(document: Document, page1_result, page1_number, page2_result) -> None:
    fields = extract_page1_fields(page1_result) if page1_result else {}

    plain_values = {name: f.value for name, f in fields.items()}
    validation_outcomes = validate_certificate_fields(plain_values)
    validation_status = overall_validation_status(validation_outcomes)
    flags_summary = build_validation_flags_summary(validation_outcomes)

    overall_confidence = _field_confidence_average(fields)
    needs_review = overall_confidence < settings.OCR_CONFIDENCE_THRESHOLD or validation_status == "failed" or any(
        f.needs_review for f in fields.values()
    )

    def val(name):
        f = fields.get(name)
        return f.value if f else None

    certificate = Certificate.objects.create(
        document=document,
        company_name=val("company_name"),
        share_type=val("share_type"),
        certificate_no=val("certificate_no"),
        share_holder_name=val("share_holder_name"),
        number_of_shares=_safe_int(val("number_of_shares")),
        face_value=_safe_decimal(val("face_value")),
        distinctive_from=val("distinctive_from"),
        distinctive_to=val("distinctive_to"),
        date_of_issue=val("date_of_issue"),
        source_file=document.original_filename,
        page_number=page1_number or 1,
        overall_confidence=overall_confidence,
        needs_review=needs_review,
        validation_status=validation_status,
        validation_flags=flags_summary,
    )

    for field_name, extracted in fields.items():
        CertificateField.objects.create(
            certificate=certificate,
            field_name=field_name,
            value=extracted.value,
            confidence=extracted.confidence,
            source=extracted.source,
            page=extracted.page,
            region=extracted.region,
            needs_review=extracted.needs_review,
        )

    if page2_result is not None:
        rows = extract_transfer_rows(page2_result, confidence_threshold=settings.OCR_CONFIDENCE_THRESHOLD)
        for row in rows:
            TransferRecord.objects.create(
                certificate=certificate,
                transfer_date=row.fields["transfer_date"][0],
                transfer_no=row.fields["transfer_no"][0],
                transferee_name=row.fields["transferee_name"][0],
                ledger_folio_no=row.fields["ledger_folio_no"][0],
                authorised_signature=row.fields["authorised_signature"][0],
                row_index=row.row_index,
                confidence=row.confidence,
                needs_review=row.needs_review,
            )
        if rows:
            latest = rows[-1]
            certificate.present_transfer_date = latest.fields["transfer_date"][0]
            certificate.present_folio_no = latest.fields["ledger_folio_no"][0]
            if latest.fields["transferee_name"][0]:
                certificate.present_share_holder_name = latest.fields["transferee_name"][0]
            certificate.save(
                update_fields=["present_transfer_date", "present_folio_no", "present_share_holder_name"]
            )

    for outcome in validation_outcomes:
        ValidationResult.objects.create(
            certificate=certificate,
            rule_name=outcome.rule_name,
            passed=outcome.passed,
            message=outcome.message,
        )


def _safe_int(value):
    try:
        return int(value) if value is not None else None
    except (ValueError, TypeError):
        return None


def _safe_decimal(value):
    try:
        return float(value) if value is not None else None
    except (ValueError, TypeError):
        return None
