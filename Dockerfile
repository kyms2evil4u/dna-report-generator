# ─────────────────────────────────────────────────────────────────
# DNA Report Generator — Dockerfile
# Multi-stage build: slim production image (~180MB)
# ─────────────────────────────────────────────────────────────────

# ── Stage 1: Builder ──────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# System deps for compilation (psycopg2, reportlab, biopython)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libpq-dev libffi-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip install --prefix=/install --no-cache-dir -r requirements.txt


# ── Stage 2: Runtime ──────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Runtime system deps only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Non-root user for security
RUN groupadd -r dna && useradd -r -g dna -d /app -s /sbin/nologin dna

WORKDIR /app

# Copy application source
COPY --chown=dna:dna . .

# Runtime directories
RUN mkdir -p /app/uploads /app/reports_output \
 && chown -R dna:dna /app/uploads /app/reports_output

USER dna

# Flask config
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_ENV=production \
    PORT=5000

EXPOSE 5000 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
  CMD curl -f http://localhost:${PORT:-5000}/api/health || exit 1

# Production server: Gunicorn — use shell form so $PORT is expanded by Railway
CMD /bin/sh -c "gunicorn --bind 0.0.0.0:${PORT:-5000} --workers 2 --worker-class gthread --threads 4 --timeout 900 --graceful-timeout 30 --keep-alive 5 --log-level info --access-logfile - --error-logfile - app:app"
