import csv
import io
import logging
import os

from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from django.utils.text import get_valid_filename
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Certificate, CertificateField, Document, OCRJob
from .serializers import (
    CertificateFieldReviewSerializer,
    CertificateSerializer,
    DocumentSerializer,
    OCRJobSerializer,
)
from .services.paddleocr_service import gpu_diagnostics, resolve_device
from .tasks import start_job_task

logger = logging.getLogger("ocr")

CSV_COLUMNS = [
    ("File name", "source_file"),
    ("Certificate No", "certificate_no"),
    ("Company Name", "company_name"),
    ("First Share Holder Name", "share_holder_name"),
    ("No of Shares", "number_of_shares"),
    ("Face Value Per Share", "face_value"),
    ("Share Type", "share_type"),
    ("From Distinctive No", "distinctive_from"),
    ("To Distinctive No", "distinctive_to"),
    ("Date of Issue", "date_of_issue"),
    ("Present Share Holder Name", "present_share_holder_name"),
    ("Present Transfer Date", "present_transfer_date"),
    ("Present Folio No", "present_folio_no"),
    ("Registered Folio No", "registered_folio_no"),
    ("Validation Status", "validation_status"),
    ("Validation Flags", "validation_flags"),
    ("Needs Review", "needs_review"),
    ("Overall Confidence", "overall_confidence"),
]


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def login_view(request):
    from django.contrib.auth import authenticate

    username = request.data.get("username")
    password = request.data.get("password")
    user = authenticate(username=username, password=password)
    if not user:
        return Response({"detail": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)
    token, _ = Token.objects.get_or_create(user=user)
    return Response({"token": token.key, "username": user.username})


class LogoutView(APIView):
    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class UploadView(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request):
        files = request.FILES.getlist("files")
        if not files:
            return Response({"detail": "No files provided"}, status=400)

        job_id = request.data.get("job")
        if job_id:
            job = OCRJob.objects.filter(pk=job_id, owner=request.user).first()
            if not job:
                return Response({"detail": "Job not found"}, status=404)
        else:
            job = OCRJob.objects.create(owner=request.user)

        created = []
        rejected = []
        for f in files:
            ext = os.path.splitext(f.name)[1].lower()
            if ext not in settings.ALLOWED_UPLOAD_EXTENSIONS:
                rejected.append({"filename": f.name, "reason": f"Unsupported file type {ext}"})
                continue
            if f.size > settings.MAX_UPLOAD_SIZE:
                rejected.append({"filename": f.name, "reason": "File exceeds maximum upload size"})
                continue
            safe_name = get_valid_filename(f.name)
            document = Document.objects.create(
                job=job,
                original_filename=safe_name,
                file=f,
                file_type=ext.lstrip("."),
                status=Document.Status.PENDING,
            )
            created.append(document)

        job.total_files = job.documents.count()
        job.save(update_fields=["total_files"])

        return Response(
            {
                "job": OCRJobSerializer(job).data,
                "documents": DocumentSerializer(created, many=True).data,
                "rejected": rejected,
            },
            status=201,
        )


class StartJobView(APIView):
    def post(self, request, job_id):
        job = OCRJob.objects.filter(pk=job_id, owner=request.user).first()
        if not job:
            return Response({"detail": "Job not found"}, status=404)

        engine = request.data.get("engine", job.engine)
        worker_count = int(request.data.get("worker_count", job.worker_count))
        if engine not in OCRJob.Engine.values:
            return Response({"detail": f"Unknown engine {engine}"}, status=400)

        job.engine = engine
        job.worker_count = worker_count
        job.status = OCRJob.Status.QUEUED
        job.save(update_fields=["engine", "worker_count", "status"])

        start_job_task.delay(job.id)
        return Response(OCRJobSerializer(job).data)


class JobActionView(APIView):
    action = None  # "pause" | "stop"

    def post(self, request, job_id):
        job = OCRJob.objects.filter(pk=job_id, owner=request.user).first()
        if not job:
            return Response({"detail": "Job not found"}, status=404)
        job.status = OCRJob.Status.PAUSED if self.action == "pause" else OCRJob.Status.STOPPED
        job.save(update_fields=["status"])
        return Response(OCRJobSerializer(job).data)


class JobDetailView(RetrieveAPIView):
    serializer_class = OCRJobSerializer

    def get_queryset(self):
        return OCRJob.objects.filter(owner=self.request.user)

    def get_object(self):
        return self.get_queryset().get(pk=self.kwargs["job_id"])


class JobResultsView(ListAPIView):
    serializer_class = CertificateSerializer

    def get_queryset(self):
        qs = Certificate.objects.filter(document__job_id=self.kwargs["job_id"], document__job__owner=self.request.user)
        if self.request.query_params.get("needs_review") == "true":
            qs = qs.filter(needs_review=True)
        return qs.order_by("id")


class JobClearView(APIView):
    def post(self, request, job_id):
        job = OCRJob.objects.filter(pk=job_id, owner=request.user).first()
        if not job:
            return Response({"detail": "Job not found"}, status=404)
        job.documents.all().delete()
        job.total_files = 0
        job.save(update_fields=["total_files"])
        return Response(status=204)


class CertificateBulkDeleteView(APIView):
    def post(self, request):
        ids = request.data.get("ids", [])
        Certificate.objects.filter(id__in=ids, document__job__owner=request.user).delete()
        return Response(status=204)


class CertificateFieldReviewView(APIView):
    def patch(self, request, field_id):
        field = CertificateField.objects.filter(
            pk=field_id, certificate__document__job__owner=request.user
        ).first()
        if not field:
            return Response({"detail": "Field not found"}, status=404)
        serializer = CertificateFieldReviewSerializer(field, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        field = serializer.save(reviewed=True, reviewed_by=request.user, reviewed_at=timezone.now())
        return Response(CertificateFieldReviewSerializer(field).data)


class JobExportView(APIView):
    def get(self, request, job_id):
        job = OCRJob.objects.filter(pk=job_id, owner=request.user).first()
        if not job:
            return Response({"detail": "Job not found"}, status=404)
        certificates = Certificate.objects.filter(document__job=job).order_by("id")

        fmt = request.query_params.get("format", "csv")
        if fmt == "xlsx":
            return _export_xlsx(certificates, f"certificates-job-{job.id}.xlsx")
        return _export_csv(certificates, f"certificates-job-{job.id}.csv")


class JobFailedExportView(APIView):
    def get(self, request, job_id):
        job = OCRJob.objects.filter(pk=job_id, owner=request.user).first()
        if not job:
            return Response({"detail": "Job not found"}, status=404)
        documents = job.documents.filter(status=Document.Status.FAILED).order_by("id")

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="certificates-failed-job-{job.id}.csv"'
        writer = csv.writer(response)
        writer.writerow(["File name", "Error Stage", "Error Type", "Error Message"])
        for doc in documents:
            writer.writerow([doc.original_filename, doc.error_stage, doc.error_type, doc.error_message])
        return response


def _export_csv(certificates, filename):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow([label for label, _ in CSV_COLUMNS])
    for cert in certificates:
        writer.writerow([getattr(cert, field) for _, field in CSV_COLUMNS])
    return response


def _export_xlsx(certificates, filename):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Certificates"
    ws.append([label for label, _ in CSV_COLUMNS])
    for cert in certificates:
        ws.append([str(getattr(cert, field)) if getattr(cert, field) is not None else "" for _, field in CSV_COLUMNS])

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    response = HttpResponse(
        buffer.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


class SystemStatusView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        diagnostics = gpu_diagnostics()
        requested = settings.OCR_DEVICE
        device = resolve_device(requested)
        return Response(
            {
                "ocr_engine": settings.OCR_ENGINE,
                "gpu_available": diagnostics["gpu_available"],
                "gpu_name": diagnostics["gpu_name"],
                "cuda_available": diagnostics["cuda_available"],
                "device": device,
                "paddle_installed": diagnostics["paddle_installed"],
                "paddle_version": diagnostics["paddle_version"],
                "paddleocr_version": diagnostics["paddleocr_version"],
                "confidence_threshold": settings.OCR_CONFIDENCE_THRESHOLD,
            }
        )
