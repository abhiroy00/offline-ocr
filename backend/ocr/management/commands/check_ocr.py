from django.conf import settings
from django.core.management.base import BaseCommand

from ocr.services.paddleocr_service import PADDLE_IMPORT_ERROR, gpu_diagnostics, resolve_device


class Command(BaseCommand):
    help = "Print OCR engine/GPU diagnostics, matching the deployment verification step."

    def handle(self, *args, **options):
        diagnostics = gpu_diagnostics()
        device = resolve_device(settings.OCR_DEVICE)

        self.stdout.write(f"OCR Engine: {settings.OCR_ENGINE}")
        self.stdout.write(f"Device: {device.upper()}")
        self.stdout.write(f"GPU: {diagnostics['gpu_name'] or 'not detected'}")
        self.stdout.write(f"CUDA: {'Available' if diagnostics['cuda_available'] else 'Not available'}")
        self.stdout.write(f"PaddlePaddle installed: {diagnostics['paddle_installed']}")
        self.stdout.write(f"PaddlePaddle version: {diagnostics['paddle_version'] or 'n/a'}")
        self.stdout.write(f"PaddleOCR version: {diagnostics['paddleocr_version'] or 'n/a'}")
        self.stdout.write(f"Worker count: {settings.CELERY_WORKER_CONCURRENCY}")

        if not diagnostics["paddle_installed"]:
            self.stdout.write(self.style.ERROR(f"Status: FAILED (PaddleOCR not installed: {PADDLE_IMPORT_ERROR})"))
            return

        self.stdout.write(self.style.SUCCESS("Status: OK"))
