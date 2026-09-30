# CPU image: local development and any deployment target without an NVIDIA
# GPU. For the EC2 GPU box, build Dockerfile.gpu instead (see that file for
# why the two can't be merged into one CUDA-version-agnostic image).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements/ requirements/
RUN pip install -r requirements/base.txt -r requirements/ocr-cpu.txt gunicorn

COPY . .

RUN python manage.py collectstatic --noinput || true

EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]
