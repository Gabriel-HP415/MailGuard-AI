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


_SUSPICIOUS_TOKENS = (
    "verify", "urgent", "click here", "password", "suspended", "limit",
    "won", "winner", "prize", "bit.ly", "tinyurl", ".tk", ".xyz",
)


def _stub_prediction(payload: PredictionRequest) -> dict[str, Any]:
    """Deterministic rule-based stand-in for the AI service.

    Used in local dev (`AI_PROVIDER=stub`) so the backend can be exercised
    end-to-end without an external AI process or API key. The output shape
    matches what `predict_service.save_prediction` expects from the AI.
    """
    import hashlib
    import random

    sender = (payload.email.sender or "").lower()
    subject = (payload.email.subject or "").lower()
    body = (payload.email.body_text or payload.email.body_html or "").lower()

    text = " ".join((sender, subject, body))
    hits = [tok for tok in _SUSPICIOUS_TOKENS if tok in text]
    risk = min(100.0, 8.0 * len(hits) + 5.0)
    is_phish = risk >= 50

    pred_class = "phishing" if is_phish else "legitimate"
    confidence = round(0.55 + min(0.4, risk / 250.0), 3)

    # Deterministic seed so the same email -> same response
    seed = int(hashlib.md5(text.encode("utf-8")).hexdigest(), 16) % (2 ** 31)
    rng = random.Random(seed)
    # Order matches constants.INDEX_TO_CLASS: normal, notification, spam, scam
    p_normal = round(rng.uniform(0.05, 0.4), 3)
    p_notif = round(rng.uniform(0.02, 0.15), 3)
    p_spam = round(rng.uniform(0.05, 0.3), 3)
    p_scam_base = 0.2 if is_phish else 0.02
    p_scam = round(min(0.95, p_scam_base + risk / 200.0), 3)

    total = p_normal + p_notif + p_spam + p_scam
    probs_dict = {
        "normal": round(p_normal / total, 4),
        "notification": round(p_notif / total, 4),
        "spam": round(p_spam / total, 4),
        "scam": round(p_scam / total, 4),
    }

    # Map to internal class enum names
    class_enum = "scam" if is_phish else "normal"

    if risk >= 75:
        threat = "critical"
    elif risk >= 50:
        threat = "high"
    elif risk >= 25:
        threat = "medium"
    else:
        threat = "low"

    return {
        "predicted_class": class_enum,
        "class_index": 3 if is_phish else 0,
        "confidence": confidence,
        "risk_score": round(risk, 2),
        "threat_level": threat,
        "probabilities": probs_dict,
        "suspicious_urls": [
            {"url": u, "score": 0.9} for u in (payload.email.links or []) if u
        ],
        "explanation": (
            {"matched_signals": hits, "note": "stub classifier"}
            if hits else None
        ),
        "model_version": "stub-v1",
    }


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

        if self.provider == "stub":
            # Local dev shortcut: deterministic stub classifier. Lets the API
            # exercise end-to-end without an external AI service or API key.
            return _stub_prediction(payload)

        # Legacy: HTTP-based AI service
        from app.api.errors import AppError

        url = f"{self.base_url}/predict"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Convert datetime objects to ISO strings for JSON serialization
                payload_dict = payload.model_dump()
                for key, value in payload_dict.items():
                    if hasattr(value, 'isoformat'):
                        payload_dict[key] = value.isoformat()
                
                # Map backend email fields to AI service format
                email_data = payload_dict.get('email', {})
                ai_payload = {
                    'subject': email_data.get('subject', ''),
                    'body': email_data.get('body_text') or email_data.get('body_html') or '',
                    'sender': email_data.get('sender', ''),
                    'sender_domain': email_data.get('sender_domain'),
                    'links': email_data.get('links'),
                }
                resp = await client.post(url, json=ai_payload)
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