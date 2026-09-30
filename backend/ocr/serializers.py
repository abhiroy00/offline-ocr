from rest_framework import serializers

from .models import Certificate, CertificateField, Document, OCRJob, TransferRecord, ValidationResult


class OCRJobSerializer(serializers.ModelSerializer):
    done_count = serializers.ReadOnlyField()
    failed_count = serializers.ReadOnlyField()
    waiting_count = serializers.ReadOnlyField()

    class Meta:
        model = OCRJob
        fields = [
            "id", "engine", "worker_count", "status", "total_files",
            "done_count", "failed_count", "waiting_count",
            "created_at", "started_at", "finished_at",
        ]
        read_only_fields = fields


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = [
            "id", "job", "original_filename", "file_type", "num_pages",
            "status", "error_stage", "error_type", "error_message",
            "uploaded_at", "processed_at",
        ]
        read_only_fields = fields


class TransferRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransferRecord
        fields = [
            "id", "transfer_date", "transfer_no", "transferee_name",
            "ledger_folio_no", "authorised_signature", "row_index",
            "confidence", "needs_review",
        ]


class CertificateFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = CertificateField
        fields = [
            "id", "field_name", "value", "confidence", "source", "page",
            "region", "needs_review", "reviewed", "reviewed_value",
            "reviewed_by", "reviewed_at",
        ]
        read_only_fields = ["id", "field_name", "confidence", "source", "page", "region"]


class ValidationResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = ValidationResult
        fields = ["rule_name", "passed", "message"]


class CertificateFieldReviewSerializer(serializers.ModelSerializer):
    """Used by the manual-review PATCH endpoint: a human edits/approves a value."""

    class Meta:
        model = CertificateField
        fields = ["reviewed_value", "reviewed"]


class CertificateSerializer(serializers.ModelSerializer):
    file = serializers.CharField(source="source_file", read_only=True)
    file_url = serializers.SerializerMethodField()
    fields_detail = CertificateFieldSerializer(source="fields", many=True, read_only=True)
    transfers = TransferRecordSerializer(many=True, read_only=True)
    validation_results = ValidationResultSerializer(many=True, read_only=True)

    def get_file_url(self, obj):
        request = self.context.get("request")
        if not obj.document or not obj.document.file:
            return None
        url = obj.document.file.url
        return request.build_absolute_uri(url) if request else url

    class Meta:
        model = Certificate
        fields = [
            "id", "file", "file_url", "source_file", "page_number",
            "company_name", "share_type", "certificate_no", "share_holder_name",
            "number_of_shares", "face_value", "distinctive_from", "distinctive_to",
            "date_of_issue", "registered_folio_no",
            "present_share_holder_name", "present_transfer_date", "present_folio_no",
            "remarks", "overall_confidence", "needs_review", "validation_status",
            "validation_flags", "fields_detail", "transfers", "validation_results",
            "created_at", "updated_at",
        ]
        read_only_fields = [f for f in fields if f not in ("remarks",)]


class SystemStatusSerializer(serializers.Serializer):
    ocr_engine = serializers.CharField()
    gpu_available = serializers.BooleanField()
    gpu_name = serializers.CharField(allow_null=True)
    cuda_available = serializers.BooleanField()
    device = serializers.CharField()
    paddle_version = serializers.CharField(allow_null=True)
    paddleocr_version = serializers.CharField(allow_null=True)
    worker_count = serializers.IntegerField()
