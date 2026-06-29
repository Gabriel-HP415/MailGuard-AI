"""HTTP client for the AI Service."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings
from app.schemas.prediction import PredictionRequest, PredictionRead

logger = logging.getLogger(__name__)


class AIServiceError(AppError := __import__("app.api.errors", fromlist=["AppError"]).AppError):
    """Raised when the AI Service fails to respond."""


_DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=5.0)


class AIServiceClient:
    """Async HTTP client wrapping the AI Service."""

    def __init__(self, base_url: str | None = None, timeout: httpx.Timeout | None = None):
        self.base_url = (base_url or "http://localhost:8001").rstrip("/")
        self.timeout = timeout or _DEFAULT_TIMEOUT

    async def predict(self, payload: PredictionRequest) -> dict[str, Any]:
        """Call the AI Service /predict endpoint."""
        from app.api.errors import AppError

        url = f"{self.base_url}/predict"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=payload.model_dump())
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error("AI service error: %s - %s", exc.response.status_code, exc.response.text)
            raise AppError(
                message=f"AI service returned {exc.response.status_code}",
                details={"body": exc.response.text[:500]},
            ) from exc
        except httpx.RequestError as exc:
            logger.error("AI service unreachable: %s", exc)
            raise AppError(message="AI service unreachable") from exc

    async def predict_batch(self, payloads: list[PredictionRequest]) -> list[dict[str, Any]]:
        """Call the AI Service /predict/batch endpoint."""
        from app.api.errors import AppError

        url = f"{self.base_url}/predict/batch"
        body = {
            "emails": [p.model_dump() for p in payloads],
            "include_explanation": payloads[0].include_explanation if payloads else True,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=body)
            resp.raise_for_status()
            data = resp.json()
            return data.get("results", [])
        except httpx.HTTPStatusError as exc:
            logger.error("AI service batch error: %s - %s", exc.response.status_code, exc.response.text)
            raise AppError(
                message=f"AI service batch returned {exc.response.status_code}",
                details={"body": exc.response.text[:500]},
            ) from exc
        except httpx.RequestError as exc:
            logger.error("AI service unreachable: %s", exc)
            raise AppError(message="AI service unreachable") from exc

    async def health(self) -> dict[str, Any]:
        """Call /health on the AI Service."""
        url = f"{self.base_url}/health"
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
        except httpx.RequestError as exc:
            return {"status": "unreachable", "error": str(exc)}


ai_client = AIServiceClient(base_url=f"http://localhost:{settings.backend_port + 1}")