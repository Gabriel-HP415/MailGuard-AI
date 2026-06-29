"""HTTP client for the AI Service.

Dispatches between providers based on ``settings.ai_provider``:

* ``gemini`` — calls Google Gemini directly (recommended for cloud).
* ``http``   — calls an external AI service over HTTP (legacy default).
* ``local``  — placeholder; real local model lives in ai_service/.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings
from app.schemas.prediction import PredictionRequest

logger = logging.getLogger(__name__)


class AIServiceError(AppError := __import__("app.api.errors", fromlist=["AppError"]).AppError):
    """Raised when the AI Service fails to respond."""


_DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=5.0)


def _email_to_gemini_inputs(payload: PredictionRequest) -> tuple[str, str, str]:
    """Map a PredictionRequest to (sender, subject, body) for Gemini."""
    email = payload.email
    sender = email.sender or ""
    subject = email.subject or ""
    body = email.body_text or email.body_html or ""
    return sender, subject, body


class AIServiceClient:
    """Async client wrapping the configured AI provider."""

    def __init__(self, base_url: str | None = None, timeout: httpx.Timeout | None = None):
        self.provider = settings.ai_provider.lower()
        self.base_url = (base_url or settings.ai_service_url).rstrip("/")
        self.timeout = timeout or _DEFAULT_TIMEOUT

    async def predict(self, payload: PredictionRequest) -> dict[str, Any]:
        if self.provider == "gemini":
            from app.services.gemini_classifier import get_gemini_classifier

            sender, subject, body = _email_to_gemini_inputs(payload)
            try:
                return await get_gemini_classifier().classify(sender, subject, body)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Gemini classification failed")
                raise AIServiceError(message=f"Gemini classification failed: {exc}") from exc

        # Legacy: HTTP-based AI service
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
        results: list[dict[str, Any]] = []
        for p in payloads:
            results.append(await self.predict(p))
        return results

    async def health(self) -> dict[str, Any]:
        """Return a liveness dict that reflects the configured provider."""
        if self.provider == "gemini":
            from app.services.gemini_classifier import get_gemini_classifier

            try:
                get_gemini_classifier()  # raises if key missing
                return {
                    "status": "ok",
                    "provider": "gemini",
                    "model": settings.gemini_model,
                }
            except Exception as exc:  # noqa: BLE001
                return {"status": "degraded", "provider": "gemini", "error": str(exc)}

        url = f"{self.base_url}/health"
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
        except httpx.RequestError as exc:
            return {"status": "unreachable", "error": str(exc)}


ai_client = AIServiceClient()