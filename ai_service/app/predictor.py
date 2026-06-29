"""High-level predictor: classifier + risk scoring + explainability."""

from __future__ import annotations

import logging
import time
from typing import Optional

from ai_service.app.constants import EmailClass, INDEX_TO_CLASS
from ai_service.app.models.classifier import EmailClassifier
from ai_service.app.models.registry import registry
from ai_service.app.preprocessing.text_cleaner import clean_text
from ai_service.app.preprocessing.url_extractor import extract_links
from ai_service.app.risk.scorer import compute_risk, threat_level_for
from ai_service.app.xai.highlighter import build_highlighted_spans
from ai_service.app.xai.summary import build_explanation_summary

logger = logging.getLogger(__name__)


class Predictor:
    """End-to-end email prediction pipeline."""

    def __init__(self, classifier: Optional[EmailClassifier] = None):
        self.classifier = classifier or registry.get_classifier()

    def predict(self, email: dict, *, include_explanation: bool = True) -> dict:
        """Classify an email dict and return a structured prediction.

        Expected `email` keys: subject, body, sender, links (optional),
        attachments (optional).
        """
        body = email.get("body") or ""
        subject = email.get("subject") or ""
        sender = email.get("sender")
        links = email.get("links") or extract_links(f"{subject}\n{body}")

        t0 = time.perf_counter()
        result = self.classifier.predict(
            {"subject": subject, "body": body, "sender": sender}
        )
        inference_ms = int((time.perf_counter() - t0) * 1000) + result.inference_time_ms

        probabilities = {
            INDEX_TO_CLASS[i]: float(p) for i, p in enumerate(result.probabilities)
        }

        clean_body = clean_text(body, max_length=10_000)
        risk = compute_risk(
            predicted_class=result.label_name,
            confidence=result.confidence,
            text=clean_body,
            links=links,
            attachments=email.get("attachments"),
        )
        threat = threat_level_for(risk.total)
        spans = build_highlighted_spans(body) if include_explanation else []
        explanation = (
            build_explanation_summary(
                predicted_class=result.label_name,
                confidence=result.confidence,
                risk=risk,
                top_keyword_hits=[],
                top_url_hits=[s for s in spans if s["category"] == "url"],
            )
            if include_explanation
            else {}
        )

        return {
            "predicted_class": result.label_name,
            "class_index": result.label_index,
            "confidence": round(result.confidence, 4),
            "probabilities": probabilities,
            "risk_score": risk.total,
            "risk_breakdown": {
                "classification": risk.classification,
                "keywords": risk.keywords,
                "urls": risk.urls,
                "attachments": risk.attachments,
            },
            "threat_level": threat,
            "inference_time_ms": inference_ms,
            "model_version": result.model_version,
            "model_algorithm": result.algorithm,
            "explanation": explanation,
            "highlighted_spans": spans,
            "suspicious_urls": [s for s in spans if s["category"] == "url"],
        }