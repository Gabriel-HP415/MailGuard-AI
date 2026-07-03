# MailGuard-AI — Render Dockerfile
#
# Pin Python 3.11 because several core dependencies (pydantic-core, bcrypt,
# some cryptography extras) do not yet ship prebuilt wheels for Python 3.14.
# Using python:3.11-slim keeps the image small (~150 MB) and avoids the
# read-only filesystem errors you get when pip tries to compile a Rust crate
# inside Render's native Python runtime.
#
# IMPORTANT — Migration strategy on Render Free tier:
# Render Free does NOT expose a Shell tab and the "Pre-Deploy Command" field
# is locked. To apply Alembic migrations on every deploy we chain them into
# the container's CMD via `sh -c`. The chain below:
#   1. Runs `alembic upgrade head` so DB schema matches the models.
#   2. Starts uvicorn bound to the port Render injected via $PORT.
# If the migration fails, uvicorn never starts and Render marks the deploy
# failed — so a half-applied schema can't crash the running API later.
#
# `exec` replaces the shell process with uvicorn so it becomes PID 1 and
# receives SIGTERM for graceful shutdown when Render stops the container.
FROM python:3.11.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps: build-essential for any wheel that still needs to compile,
# libpq for psycopg2, default-libmysqlclient-dev for pymysql.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    default-libmysqlclient-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

# Create logs directory (the app writes logs/app.log on startup).
RUN mkdir -p logs && chmod -R 755 logs

EXPOSE 8000

# Render injects $PORT; default 8000 for local testing.
#
# We use `sh -c` to chain `alembic upgrade head` before uvicorn boots. The
# `&&` makes the chain fail-fast: if migration fails, uvicorn never starts,
# Render retries the deploy, and the existing app stays on the previous
# (working) revision instead of crashing on a half-applied schema.
#
# The `|| true` after uvicorn keeps the shell exit code 0 on a clean uvicorn
# shutdown so Render doesn't record a spurious crash. `exec` replaces the
# shell with uvicorn so it becomes PID 1 and receives SIGTERM directly.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]