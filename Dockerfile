# One container image for the whole application: the React build is served by FastAPI, so a
# single web service (Render, AWS App Runner / ECS, Azure Container Apps, Google Cloud Run)
# hosts the frontend and the REST API on one URL.
#
#   docker build -t diet-planner .
#   docker run --rm -p 8000:8000 -e JWT_SECRET_KEY=<random 32+ chars> diet-planner
#
# Configuration (database, object storage, AI provider) comes from environment variables at
# run time; the image itself contains no secrets.

# --- Stage 1: build the React frontend ------------------------------------------------------
FROM node:22-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# --- Stage 2: Python runtime ----------------------------------------------------------------
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    ENVIRONMENT=production \
    LOG_FORMAT=json \
    FRONTEND_DIST_DIR=/app/frontend/dist \
    PORT=8000

WORKDIR /app

# Dependencies first, so code changes don't invalidate this (slow) layer.
COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY backend/ backend/
COPY ai_engine/ ai_engine/
COPY cloud/ cloud/
COPY --from=frontend /build/dist frontend/dist

# Run as an unprivileged user. ./data holds the SQLite file and the simulated bucket when no
# cloud database / object storage is configured (ephemeral: lost when the container stops).
RUN useradd --create-home --uid 10001 appuser && mkdir -p data && chown appuser:appuser data
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", \"8000\")}/api/health', timeout=4)"

# Hosting platforms inject PORT; --proxy-headers lets uvicorn see HTTPS behind their proxy.
CMD ["sh", "-c", "exec uvicorn backend.app:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
