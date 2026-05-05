# ============================================================
# Customer Success Digital FTE — Kafka Consumer Worker
# Multi-stage build for minimal image size.
# ============================================================

# ── Stage 1: Build dependencies ─────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# Build-time deps for psycopg (libpq) and C extensions
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: Runtime ────────────────────────────────────────
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Runtime-only system deps (libpq for psycopg)
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 && \
    rm -rf /var/lib/apt/lists/*

# Copy pre-built Python packages from builder
COPY --from=builder /install /usr/local

# Copy application code and database schema
COPY app/ app/
COPY database/ database/

# Run as non-root user
RUN adduser --disabled-password --no-create-home --gecos "" appuser
USER appuser

# No EXPOSE — worker has no HTTP server
# No HEALTHCHECK — Kafka consumer is monitored via consumer group lag

CMD ["python", "-m", "app.workers.worker"]
