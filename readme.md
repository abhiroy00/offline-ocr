# Offline Share Certificate OCR

A self-hosted Share Certificate OCR platform. **No OpenAI, no LLM, no external
AI API is called anywhere in this pipeline.** All OCR and extraction runs on
your own server using PaddleOCR + OpenCV + deterministic rule-based parsing.

> **Note on project history:** this repository was empty when this system was
> built (no prior code to preserve) — the "existing OpenAI-based app" this
> replaces runs only on a separate EC2 instance this session did not have
> working SSH access to (see "Known limitations" below). Everything here is a
> fresh implementation designed to match the UI/CSV/PDF samples provided.

## Architecture

```
Upload -> Django API -> file validation -> PDF/image render (PyMuPDF)
       -> OpenCV adaptive preprocessing -> PaddleOCR (GPU or CPU)
       -> page classification -> rule-based field extraction
       -> transfer-table extraction -> validation engine
       -> confidence scoring -> PostgreSQL -> CSV/Excel export
```

Celery + Redis handle batch processing so one bad file never blocks the rest
of a batch. See `backend/ocr/services/` for each pipeline stage as its own
testable module, and `backend/ocr/services/pipeline.py` for the orchestrator
Celery tasks call.

- **Backend:** Django + DRF + Celery + Redis + PostgreSQL (`backend/`)
- **OCR:** PaddleOCR with automatic GPU/CPU device selection (`ocr/services/paddleocr_service.py`)
- **Extraction:** regex + keyword + region-based rules, no ML/LLM (`ocr/services/extraction_service.py`, `table_extraction_service.py`)
- **Validation:** deterministic rule checks, e.g. `To - From + 1 == shares` (`ocr/services/validation_service.py`)
- **Frontend:** React + Vite + Tailwind (`frontend/`), matching the original UI layout
- **No-fabrication policy:** every extractor returns `None` + `needs_review=True` rather than guessing — enforced by tests (see `ocr/tests/test_extraction_service.py`, `test_benchmark.py`)

## Local development

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate   # or venv\Scripts\activate on Windows
pip install -r requirements/base.txt -r requirements/ocr-cpu.txt -r requirements/dev.txt
cp .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver

# Celery (separate terminal, needs Redis running)
celery -A config worker --loglevel=info

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Or via Docker Compose (CPU-only dev stack): `docker compose up --build`.

## Tests

```bash
cd backend
pytest                       # unit tests always run; OCR-integration tests
                              # auto-skip unless requirements/ocr-cpu.txt is
                              # installed (see ocr/tests/conftest.py)
python manage.py check_ocr    # OCR engine / GPU diagnostics
python manage.py run_benchmark  # regenerates tests/fixtures/accuracy_report.{json,csv}
```

45 tests currently pass locally with PaddleOCR installed, including a full
HTTP-level test that uploads a real sample certificate, runs the real
PaddleOCR pipeline (no mocks), and checks the resulting CSV export.

## Deployment (EC2, GPU)

1. `nvidia-smi` — confirm driver + GPU are visible.
2. Check CUDA version and pick the matching PaddlePaddle GPU wheel — see
   `backend/requirements/ocr-gpu.txt` for exact commands (deliberately not a
   blind `pip install -r`, since the correct wheel depends on the installed
   CUDA version).
3. `docker compose -f docker-compose.prod.yml up --build -d` (requires the
   NVIDIA Container Toolkit on the host — see comments in that file).
4. `python manage.py check_ocr` inside the `celery` container to confirm
   `Device: GPU` and `Status: OK`.
5. `python manage.py migrate` and `createsuperuser`.

CI/CD (`.github/workflows/ci.yml`) runs lint + tests + Docker builds on every
push, and includes a deploy job that SSHes into EC2 and redeploys on push to
`main` — it no-ops until you add `EC2_HOST`, `EC2_USER`, `EC2_SSH_KEY`, and
`EC2_APP_DIR` as repo secrets (deliberately not something this session
configured on your behalf).

## Known limitations (honest accounting, not hidden)

Benchmarked against the 4 supplied sample certificates (1605-1608.pdf):

- **Printed fields are reliable:** company name, holder name, share count,
  face value, share type, and issue date extract consistently and correctly
  across all 4 samples.
- **Certificate number** is occasionally missed on faded scans (1605, 1607)
  — correctly flagged `needs_review`, not guessed.
- **Distinctive numbers** (handwritten, faint on all 4 samples) are mostly
  unreadable to OCR and correctly returned as `None` + `needs_review=True`
  rather than fabricated — this matches the original OpenAI-based system's
  own "Distinctive numbers missing/unreadable" flag on these exact files.
- **Company name** OCRs as "KAMANIMETALSEALLOYS" (spaces and "&" lost) due
  to the decorative banner font — faithful to what PaddleOCR actually read,
  not further corrected, since guessing word boundaries would risk
  fabrication.
- **Page-2 transfer table**: these scans have handwritten, sometimes
  struck-through/superseded entries with no ruled grid lines, which is a
  genuinely hard layout problem. The extractor does its best at row
  clustering and correctly flags low-confidence rows for manual review
  rather than presenting a falsely-clean table.
- **EC2 access:** this session was given a `.pem` key (`new-ocr.pem`) that
  did not match the running instance's actual key pair (`share-ocr-new`),
  and the provided AWS API credentials lack `ec2-instance-connect` and IAM
  permissions to self-remediate. The app was built fresh in this repo
  instead of edited in place on the server. To deploy, either provide the
  correct SSH key or use AWS Console → EC2 → Connect → EC2 Instance Connect.
