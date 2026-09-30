import pytest
from django.urls import reverse

from ocr.models import Certificate, Document, OCRJob
from ocr.tests.conftest import fixture_path, requires_paddleocr


@pytest.mark.django_db
def test_login_requires_valid_credentials(api_client, django_user_model):
    django_user_model.objects.create_user(username="alice", password="correct-horse")
    resp = api_client.post(reverse("login"), {"username": "alice", "password": "wrong"})
    assert resp.status_code == 401

    resp = api_client.post(reverse("login"), {"username": "alice", "password": "correct-horse"})
    assert resp.status_code == 200
    assert "token" in resp.data


@pytest.mark.django_db
def test_login_establishes_session_for_plain_link_downloads(api_client, django_user_model):
    """Regression test: CSV/Excel export and 'open uploaded scan' are plain
    <a href> links in the UI -- normal browser navigation, which can't carry
    the Authorization header our axios client attaches to API calls. They
    only work if login also establishes a session cookie. Found live: every
    download link 401'd even while logged in via the token.
    """
    user = django_user_model.objects.create_user(username="bob", password="correct-horse")
    job = OCRJob.objects.create(owner=user)

    resp = api_client.post(reverse("login"), {"username": "bob", "password": "correct-horse"})
    assert resp.status_code == 200

    # Deliberately do NOT set an Authorization header -- rely only on the
    # session cookie the test client now holds, exactly like a plain link click.
    resp = api_client.get(reverse("ocr-job-export", args=[job.id]))
    assert resp.status_code == 200
    assert resp["Content-Type"] == "text/csv"


@pytest.mark.django_db
def test_system_status_reports_engine_without_auth(api_client):
    resp = api_client.get(reverse("ocr-system-status"))
    assert resp.status_code == 200
    assert resp.data["ocr_engine"] == "PADDLEOCR"
    assert "gpu_available" in resp.data


@pytest.mark.django_db
def test_upload_rejects_unsupported_extension(auth_client):
    client, _ = auth_client
    from django.core.files.uploadedfile import SimpleUploadedFile

    bad_file = SimpleUploadedFile("virus.exe", b"not a certificate", content_type="application/octet-stream")
    resp = client.post(reverse("ocr-upload"), {"files": [bad_file]}, format="multipart")
    assert resp.status_code == 201
    assert resp.data["documents"] == []
    assert resp.data["rejected"][0]["filename"] == "virus.exe"


@pytest.mark.django_db
def test_upload_creates_job_and_documents(auth_client, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    client, _ = auth_client
    from django.core.files.uploadedfile import SimpleUploadedFile

    with open(fixture_path("1608.pdf"), "rb") as fh:
        upload = SimpleUploadedFile("1608.pdf", fh.read(), content_type="application/pdf")

    resp = client.post(reverse("ocr-upload"), {"files": [upload]}, format="multipart")
    assert resp.status_code == 201
    assert len(resp.data["documents"]) == 1
    job_id = resp.data["job"]["id"]
    assert OCRJob.objects.get(pk=job_id).total_files == 1
    assert Document.objects.filter(job_id=job_id, status=Document.Status.PENDING).exists()


@requires_paddleocr
@pytest.mark.django_db
def test_full_pipeline_via_api_produces_reviewable_certificate(auth_client, settings, tmp_path):
    """End-to-end: upload -> start -> results -> CSV export, through the real
    HTTP API, running actual PaddleOCR (CPU) against the real sample PDF --
    no mocking of the OCR engine."""
    settings.MEDIA_ROOT = str(tmp_path)
    client, user = auth_client

    with open(fixture_path("1608.pdf"), "rb") as fh:
        upload = fh.read()
    from django.core.files.uploadedfile import SimpleUploadedFile

    resp = client.post(
        reverse("ocr-upload"),
        {"files": [SimpleUploadedFile("1608.pdf", upload, content_type="application/pdf")]},
        format="multipart",
    )
    job_id = resp.data["job"]["id"]

    resp = client.post(
        reverse("ocr-job-start", args=[job_id]), {"engine": "paddleocr_cpu", "worker_count": 1}
    )
    assert resp.status_code == 200

    job = OCRJob.objects.get(pk=job_id)
    assert job.status == OCRJob.Status.COMPLETE  # ran synchronously (CELERY_TASK_ALWAYS_EAGER)
    assert job.done_count == 1

    resp = client.get(reverse("ocr-job-results", args=[job_id]))
    assert resp.status_code == 200
    assert resp.data["count"] == 1
    certificate = Certificate.objects.get(document__job_id=job_id)
    assert certificate.certificate_no == "OB1608"
    assert certificate.number_of_shares == 25
    assert certificate.face_value == 10
    assert certificate.date_of_issue == "1967-08-14"
    # Distinctive numbers are genuinely unreadable handwriting on this scan --
    # the pipeline must flag it, not invent a value.
    assert certificate.distinctive_from is None
    assert certificate.needs_review is True

    resp = client.get(reverse("ocr-job-export", args=[job_id]))
    assert resp.status_code == 200
    assert b"OB1608" in resp.content
    assert resp["Content-Type"] == "text/csv"
