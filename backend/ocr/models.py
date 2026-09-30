import uuid

from django.conf import settings
from django.db import models


def upload_path(instance, filename):
    return f"uploads/{instance.job_id}/{uuid.uuid4().hex}_{filename}"


class OCRJob(models.Model):
    class Engine(models.TextChoices):
        PADDLEOCR_GPU = "paddleocr_gpu", "PaddleOCR (NVIDIA GPU)"
        PADDLEOCR_CPU = "paddleocr_cpu", "PaddleOCR (CPU)"

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        PAUSED = "paused", "Paused"
        STOPPED = "stopped", "Stopped"
        COMPLETE = "complete", "Complete"
        FAILED = "failed", "Failed"

    id = models.BigAutoField(primary_key=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    engine = models.CharField(max_length=32, choices=Engine.choices, default=Engine.PADDLEOCR_CPU)
    worker_count = models.PositiveSmallIntegerField(default=8)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED)
    total_files = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"OCRJob #{self.id} ({self.status})"

    @property
    def done_count(self):
        return self.documents.filter(status=Document.Status.DONE).count()

    @property
    def failed_count(self):
        return self.documents.filter(status=Document.Status.FAILED).count()

    @property
    def waiting_count(self):
        return self.documents.filter(
            status__in=[Document.Status.PENDING, Document.Status.PROCESSING]
        ).count()


class Document(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"

    class Stage(models.TextChoices):
        UPLOAD = "upload", "Upload"
        PDF_CONVERSION = "pdf_conversion", "PDF conversion"
        PREPROCESSING = "preprocessing", "Preprocessing"
        OCR = "ocr", "OCR"
        EXTRACTION = "extraction", "Extraction"
        VALIDATION = "validation", "Validation"
        DATABASE = "database", "Database"
        EXPORT = "export", "Export"

    id = models.BigAutoField(primary_key=True)
    job = models.ForeignKey(OCRJob, related_name="documents", on_delete=models.CASCADE)
    original_filename = models.CharField(max_length=255)
    file = models.FileField(upload_to=upload_path, max_length=500)
    file_type = models.CharField(max_length=16)
    num_pages = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    error_stage = models.CharField(max_length=32, choices=Stage.choices, blank=True)
    error_type = models.CharField(max_length=128, blank=True)
    error_message = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.original_filename


class Certificate(models.Model):
    class ValidationStatus(models.TextChoices):
        PASSED = "passed", "Passed"
        FAILED = "failed", "Failed"
        UNKNOWN = "unknown", "Unknown"

    id = models.BigAutoField(primary_key=True)
    document = models.ForeignKey(Document, related_name="certificates", on_delete=models.CASCADE)

    company_name = models.CharField(max_length=255, blank=True, null=True)
    share_type = models.CharField(max_length=64, blank=True, null=True)
    certificate_no = models.CharField(max_length=64, blank=True, null=True)
    share_holder_name = models.CharField(max_length=255, blank=True, null=True)
    number_of_shares = models.IntegerField(blank=True, null=True)
    face_value = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    distinctive_from = models.CharField(max_length=32, blank=True, null=True)
    distinctive_to = models.CharField(max_length=32, blank=True, null=True)
    # normalized to YYYY-MM-DD; kept as text so an unparsed raw value can still be stored
    date_of_issue = models.CharField(max_length=32, blank=True, null=True)

    registered_folio_no = models.CharField(max_length=64, blank=True, null=True)
    present_share_holder_name = models.CharField(max_length=255, blank=True, null=True)
    present_transfer_date = models.CharField(max_length=32, blank=True, null=True)
    present_folio_no = models.CharField(max_length=64, blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)

    source_file = models.CharField(max_length=255, blank=True)
    page_number = models.PositiveSmallIntegerField(default=1)

    overall_confidence = models.FloatField(default=0.0)
    needs_review = models.BooleanField(default=False)
    validation_status = models.CharField(
        max_length=16, choices=ValidationStatus.choices, default=ValidationStatus.UNKNOWN
    )
    validation_flags = models.TextField(blank=True)  # human-readable summary, matches existing CSV column

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"Certificate {self.certificate_no or '?'} ({self.source_file})"


FIELD_NAME_CHOICES = [
    ("certificate_no", "Certificate No"),
    ("company_name", "Company Name"),
    ("share_holder_name", "Share Holder Name"),
    ("number_of_shares", "Number of Shares"),
    ("face_value", "Face Value"),
    ("share_type", "Share Type"),
    ("date_of_issue", "Date of Issue"),
    ("distinctive_from", "Distinctive From"),
    ("distinctive_to", "Distinctive To"),
    ("registered_folio_no", "Registered Folio No"),
]


class CertificateField(models.Model):
    """Per-field extraction detail, used to drive the manual-review UI."""

    id = models.BigAutoField(primary_key=True)
    certificate = models.ForeignKey(Certificate, related_name="fields", on_delete=models.CASCADE)
    field_name = models.CharField(max_length=64, choices=FIELD_NAME_CHOICES)
    value = models.TextField(blank=True, null=True)
    confidence = models.FloatField(blank=True, null=True)
    source = models.CharField(max_length=32, default="paddleocr")  # paddleocr | regex | manual
    page = models.PositiveSmallIntegerField(default=1)
    region = models.CharField(max_length=64, blank=True)
    needs_review = models.BooleanField(default=False)

    reviewed = models.BooleanField(default=False)
    reviewed_value = models.TextField(blank=True, null=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("certificate", "field_name")

    def __str__(self):
        return f"{self.certificate_id}:{self.field_name}"


class TransferRecord(models.Model):
    id = models.BigAutoField(primary_key=True)
    certificate = models.ForeignKey(Certificate, related_name="transfers", on_delete=models.CASCADE)
    transfer_date = models.CharField(max_length=32, blank=True, null=True)
    transfer_no = models.CharField(max_length=64, blank=True, null=True)
    transferee_name = models.CharField(max_length=255, blank=True, null=True)
    ledger_folio_no = models.CharField(max_length=64, blank=True, null=True)
    authorised_signature = models.CharField(max_length=255, blank=True, null=True)
    row_index = models.PositiveSmallIntegerField(default=0)
    confidence = models.FloatField(default=0.0)
    needs_review = models.BooleanField(default=False)

    class Meta:
        ordering = ["certificate_id", "row_index"]

    def __str__(self):
        return f"Transfer {self.row_index} of certificate {self.certificate_id}"


class ValidationResult(models.Model):
    id = models.BigAutoField(primary_key=True)
    certificate = models.ForeignKey(Certificate, related_name="validation_results", on_delete=models.CASCADE)
    rule_name = models.CharField(max_length=64)
    passed = models.BooleanField()
    message = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.rule_name}: {'OK' if self.passed else 'FAILED'}"
