# syntax=docker/dockerfile:1.7

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/opt/venv/bin:$PATH" \
    TORCH_HOME=/app/.cache/torch

WORKDIR /app

# Only install build deps here (not runtime)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv

# =========================
# Dependencies stage
# =========================
FROM base AS deps

COPY requirements.txt .

# Remove torch from requirements (we install separately)
RUN python - <<'PY'
from pathlib import Path
reqs = Path("requirements.txt").read_text().splitlines()
filtered = [r for r in reqs if r.strip() and not r.startswith(("torch==","torchvision=="))]
Path("requirements.runtime.txt").write_text("\n".join(filtered) + "\n")
PY

# Use BuildKit cache (FAST builds)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip setuptools wheel

# Install torch separately (better caching)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install \
    --index-url https://download.pytorch.org/whl/cpu \
    torch==2.7.0 \
    torchvision==0.22.0

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.runtime.txt

# =========================
# Runtime (SMALL IMAGE)
# =========================
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    TORCH_HOME=/app/.cache/torch

WORKDIR /app

# ONLY runtime libs (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=deps /opt/venv /opt/venv

# Copy only required code
COPY app ./app
COPY worker ./worker

# Create runtime dirs
RUN mkdir -p /app/uploads /app/outputs /app/models

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]