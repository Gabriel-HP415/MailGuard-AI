"""Google Gemini-based spam/phishing classifier.

Used when ``AI_PROVIDER=gemini`` (recommended for cloud deployments where
running a local DistilBERT model is not feasible). This implementation is a
small, dependency-light wrapper around the public Gemini REST endpoint so
we don't require the full ``google-generativeai`` SDK at deploy time.

Endpoint: https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent
Auth:     ?key=$GEMINI_API_KEY
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)

# Class set kept identical to backend/app/core/constants.py::EmailClass
_LABELS = ["safe", "spam", "phishing", "malware", "social_engineering"]

_PROMPT_TEMPLATE = """You are an email security analyst. Classify the email below into exactly one of:
{labels}

Return STRICT JSON only (no prose, no markdown fences) with this exact shape:
{{
  "predicted_class": "<one of {labels}>",
  "confidence": <float between 0 and 1>,
  "risk_score": <float between 0 and 1 — overall maliciousness>,
  "explanation": "<1-2 sentences in plain English>",
  "suspicious_urls": [<list of URLs found in the email that look suspicious, with a short reason each>],
  "highlighted_spans": [<list of {{"text": "...", "reason": "..."}} for risky phrases>],
  "threat_level": "<one of: low, medium, high, critical>"
}}

Email:
From: {sender}
Subject: {subject}
Body:
\"\"\"
{body}
\"\"\"
"""


def _extract_json(text: str) -> dict[str, Any]:
    """Robustly extract a JSON object from a model response."""
    if not text:
        raise ValueError("Empty Gemini response")
    # Strip ```json ... ``` fences if present
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fenced:
        text = fenced.group(1)
    else:
        # Find the outermost {...}
        first = text.find("{")
        last = text.rfind("}")
        if first != -1 and last != -1 and last > first:
            text = text[first : last + 1]
    return json.loads(text)


class GeminiClassifier:
    """Async client wrapping Gemini for email classification."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 20.0,
    ):
        self.api_key = api_key or settings.gemini_api_key
        self.model = model or settings.gemini_model
        self.timeout = timeout
        if not self.api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Set it in env or .env to use the Gemini provider."
            )

    def _build_prompt(self, sender: str, subject: str, body: str) -> str:
        return _PROMPT_TEMPLATE.format(
            labels=", ".join(_LABELS),
            sender=(sender or "(unknown)"),
            subject=(subject or "(no subject)"),
            body=(body or "")[:4000],  # cap to avoid token bloat
        )

    async def classify(self, sender: str, subject: str, body: str) -> dict[str, Any]:
        """Return a normalized prediction dict matching ``PredictionRead``."""
        url = GEMINI_ENDPOINT.format(model=self.model)
        params = {"key": self.api_key}
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": self._build_prompt(sender, subject, body)},
                    ],
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "topP": 0.9,
                "maxOutputTokens": 1024,
            },
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, params=params, json=payload)
        if resp.status_code >= 400:
            logger.error("Gemini error %s: %s", resp.status_code, resp.text[:500])
            raise RuntimeError(
                f"Gemini API returned {resp.status_code}: {resp.text[:300]}"
            )
        data = resp.json()
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as exc:
            logger.error("Unexpected Gemini response shape: %s", data)
            raise RuntimeError("Gemini returned an unexpected payload") from exc

        parsed = _extract_json(text)
        # Normalize + defaults
        predicted = str(parsed.get("predicted_class", "safe")).lower().strip()
        if predicted not in _LABELS:
            predicted = "safe"
        confidence = float(parsed.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))
        risk_score = float(parsed.get("risk_score", confidence))
        risk_score = max(0.0, min(1.0, risk_score))
        return {
            "predicted_class": predicted,
            "class_index": _LABELS.index(predicted),
            "confidence": confidence,
            "risk_score": risk_score,
            "threat_level": str(parsed.get("threat_level", "medium")).lower(),
            "explanation": parsed.get("explanation"),
            "suspicious_urls": parsed.get("suspicious_urls") or [],
            "highlighted_spans": parsed.get("highlighted_spans") or [],
            "model_version": f"gemini:{self.model}",
        }


_gemini_singleton: GeminiClassifier | None = None


def get_gemini_classifier() -> GeminiClassifier:
    """Lazy singleton accessor."""
    global _gemini_singleton
    if _gemini_singleton is None:
        _gemini_singleton = GeminiClassifier()
    return _gemini_singleton