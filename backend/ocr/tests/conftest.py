import os

import pytest

from ocr.services.paddleocr_service import PADDLE_IMPORT_ERROR

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "tests", "fixtures")

requires_paddleocr = pytest.mark.skipif(
    PADDLE_IMPORT_ERROR is not None,
    reason=(
        "PaddleOCR not installed in this environment (CI runs the fast unit "
        "suite only; install requirements/ocr-cpu.txt to run this locally)."
    ),
)


@pytest.fixture
def api_client():
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture
def auth_client(db, api_client, django_user_model):
    user = django_user_model.objects.create_user(username="reviewer", password="test-pass-123")
    api_client.force_authenticate(user=user)
    return api_client, user


def fixture_path(filename: str) -> str:
    return os.path.join(FIXTURES_DIR, filename)
