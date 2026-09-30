from django.contrib import admin

from .models import Certificate, CertificateField, Document, OCRJob, TransferRecord, ValidationResult


@admin.register(OCRJob)
class OCRJobAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "engine", "total_files", "created_at")
    list_filter = ("status", "engine")


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "original_filename", "job", "status", "num_pages", "uploaded_at")
    list_filter = ("status",)
    search_fields = ("original_filename",)


class CertificateFieldInline(admin.TabularInline):
    model = CertificateField
    extra = 0


class TransferRecordInline(admin.TabularInline):
    model = TransferRecord
    extra = 0


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "certificate_no",
        "company_name",
        "share_holder_name",
        "number_of_shares",
        "needs_review",
        "validation_status",
    )
    list_filter = ("needs_review", "validation_status", "share_type")
    search_fields = ("certificate_no", "company_name", "share_holder_name", "source_file")
    inlines = [CertificateFieldInline, TransferRecordInline]


@admin.register(ValidationResult)
class ValidationResultAdmin(admin.ModelAdmin):
    list_display = ("certificate", "rule_name", "passed", "message")
    list_filter = ("passed", "rule_name")
