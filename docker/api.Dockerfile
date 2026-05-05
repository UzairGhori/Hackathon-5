# ============================================================
# Customer Success Digital FTE — FastAPI Server
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

# Runtime-only system deps (libpq for psycopg, curl for healthcheck)
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 curl && \
    rm -rf /var/lib/apt/lists/*

# Copy pre-built Python packages from builder
COPY --from=builder /install /usr/local

# Copy application code, database schema, and static assets
COPY app/ app/
COPY database/ database/
COPY static/ static/

# Run as non-root user
RUN adduser --disabled-password --no-create-home --gecos "" appuser
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health/live || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
