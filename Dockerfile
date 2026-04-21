# ============================================================
# Customer Success Digital FTE — Default Application Image
#
# This is a convenience Dockerfile for standalone builds.
# For docker-compose, the per-service Dockerfiles in docker/
# are used instead:
#   docker/api.Dockerfile       — FastAPI server
#   docker/worker.Dockerfile    — Kafka consumer worker
#   docker/postgres.Dockerfile  — PostgreSQL 16 + pgvector
#   docker/kafka.Dockerfile     — Confluent Kafka broker
#
# Standalone usage:
#   docker build -t cs-api .
#   docker run -p 8000:8000 --env-file .env cs-api
# ============================================================

FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Runtime ──────────────────────────────────────────────────
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 curl && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

COPY app/ app/
COPY database/ database/

RUN adduser --disabled-password --no-create-home --gecos "" appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
