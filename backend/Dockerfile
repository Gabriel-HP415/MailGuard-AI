# MailGuard-AI — Render Dockerfile
#
# Pin Python 3.11 because several core dependencies (pydantic-core, bcrypt,
# some cryptography extras) do not yet ship prebuilt wheels for Python 3.14.
# Using python:3.11-slim keeps the image small (~150 MB) and avoids the
# read-only filesystem errors you get when pip tries to compile a Rust crate
# inside Render's native Python runtime.
FROM python:3.11.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps: build-essential for any wheel that still needs to compile,
# libpq for psycopg2.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

EXPOSE 8000

# Render injects $PORT; default 8000 for local testing.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]