import logging

from celery import shared_task
from django.db import close_old_connections

from ocr.models import Document, OCRJob
from ocr.services.pipeline import process_document

logger = logging.getLogger("ocr")


@shared_task(bind=True, max_retries=0)
def process_document_task(self, document_id: int, engine_device: str = "auto"):
    """One Celery task per document -- a single bad file only fails its own
    row, never the rest of the batch."""
    close_old_connections()
    try:
        document = Document.objects.select_related("job").get(pk=document_id)
        if document.job.status == OCRJob.Status.STOPPED:
            logger.info("[OCR] Document %s: skipped, job was stopped", document_id)
            return
        process_document(document_id, engine_device=engine_device)
        _maybe_complete_job(document_id)
    finally:
        close_old_connections()


def _maybe_complete_job(document_id: int) -> None:
    from django.utils import timezone

    document = Document.objects.select_related("job").get(pk=document_id)
    job = document.job
    if job.status in (OCRJob.Status.PAUSED, OCRJob.Status.STOPPED):
        return
    if job.waiting_count == 0:
        job.status = OCRJob.Status.COMPLETE
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "finished_at"])


@shared_task
def start_job_task(job_id: int):
    close_old_connections()
    job = OCRJob.objects.get(pk=job_id)
    device = "gpu" if job.engine == OCRJob.Engine.PADDLEOCR_GPU else "cpu"
    job.status = OCRJob.Status.RUNNING
    from django.utils import timezone

    job.started_at = timezone.now()
    job.save(update_fields=["status", "started_at"])

    for document in job.documents.filter(status=Document.Status.PENDING):
        job.refresh_from_db(fields=["status"])
        if job.status in (OCRJob.Status.PAUSED, OCRJob.Status.STOPPED):
            logger.info("[OCR] Job %s: dispatch loop halted (%s)", job.id, job.status)
            break
        process_document_task.delay(document.id, engine_device=device)
