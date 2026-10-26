# ==============================================================================
# Multi-Stage Production Dockerfile for Amrutam Telemedicine Backend
# ==============================================================================

# Stage 1: Build stage
FROM python:3.12-slim-bookworm AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Minimal Production Runtime
FROM python:3.12-slim-bookworm AS runner

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/home/amrutam/.local/bin:$PATH"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    netcat-traditional \
    && rm -rf /var/lib/apt/lists/*

# Security: Create non-root system user
RUN groupadd -g 10001 amrutam && \
    useradd -u 10001 -g amrutam -m -s /bin/bash amrutam

# Copy installed python dependencies from builder
COPY --from=builder --chown=amrutam:amrutam /root/.local /home/amrutam/.local

# Copy application source code
COPY --chown=amrutam:amrutam . .

USER amrutam

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/api/v1/health/live/ || exit 1

CMD ["gunicorn", "amrutam_core.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4", "--threads", "2", "--timeout", "60", "--access-logfile", "-", "--error-logfile", "-"]
