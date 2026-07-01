FROM python:3.11-slim

# System dependencies (for torch, sklearn, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        && rm -rf /var/lib/apt/lists/*

# Workdir
WORKDIR /app

# Python deps first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . /app/ai_service

# Models + datasets directories (mounted as volumes in production)
RUN mkdir -p /app/ai_service/models/artifacts /app/ai_service/datasets

ENV PYTHONPATH=/app/ai_service
ENV PYTHONUNBUFFERED=1

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8001/health || exit 1

CMD ["uvicorn", "ai_service.app.main:app", "--host", "0.0.0.0", "--port", "8001"]
