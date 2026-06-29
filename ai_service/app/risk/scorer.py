"""Risk scoring utilities: combine classification + URL/keyword signals into a 0-100 score."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import numpy as np

from ai_service.app.config import settings
from ai_service.app.constants import KEYWORD_WEIGHTS, EmailClass
from ai_service.app.preprocessing.url_extractor import analyze_url, extract_links

logger = logging.getLogger(__name__)


@dataclass
class RiskBreakdown:
    """Per-component risk contributions."""

    classification: float
    keywords: float
    urls: float
    attachments: float
    total: float


def _class_base_score(predicted_class: str, confidence: float) -> float:
    """Base score derived from the classifier's output (0-70 range)."""
    if predicted_class == EmailClass.SCAM.value:
        return 50.0 + 20.0 * confidence
    if predicted_class == EmailClass.SPAM.value:
        return 30.0 + 20.0 * confidence
    if predicted_class == EmailClass.NOTIFICATION.value:
        return 5.0
    return 0.0


def _keyword_score(text: str) -> tuple[float, list[dict]]:
    """Compute risk score from suspicious keyword occurrences."""
    if not text:
        return 0.0, []
    text_l = text.lower()
    score = 0.0
    hits: list[dict] = []
    for phrase, weight in KEYWORD_WEIGHTS.items():
        if phrase in text_l:
            count = text_l.count(phrase)
            score += weight * min(count, 3)  # cap at 3 occurrences
            hits.append({"keyword": phrase, "weight": weight, "count": count})
    return min(score, 30.0), hits


def _url_score(urls: list[str]) -> tuple[float, list[dict]]:
    """Compute risk score from URLs found in the email."""
    if not urls:
        return 0.0, []
    total = 0.0
    details: list[dict] = []
    for u in urls:
        a = analyze_url(u)
        if a.risk_score > 0:
            total += a.risk_score
            details.append(
                {
                    "url": a.url,
                    "domain": a.domain,
                    "risk": a.risk_score,
                    "reasons": a.reasons,
                }
            )
    return min(total, 40.0), details


def _attachment_score(attachments: list[dict] | None) -> float:
    """Add risk for high-risk attachment types."""
    if not attachments:
        return 0.0
    risky_ext = {".exe", ".bat", ".cmd", ".scr", ".js", ".vbs", ".jar", ".zip", ".rar", ".7z", ".iso"}
    score = 0.0
    for att in attachments:
        name = (att.get("name") or "").lower() if isinstance(att, dict) else str(att).lower()
        for ext in risky_ext:
            if name.endswith(ext):
                score += 5.0
                break
    return min(score, 15.0)


def compute_risk(
    *,
    predicted_class: str,
    confidence: float,
    text: str,
    links: list[str] | None = None,
    attachments: list[dict] | None = None,
) -> RiskBreakdown:
    """Combine all signals into a 0-100 risk score with per-component breakdown."""
    class_part = _class_base_score(predicted_class, confidence)
    keyword_part, _ = _keyword_score(text)
    urls = links if links is not None else extract_links(text or "")
    url_part, _ = _url_score(urls)
    attach_part = _attachment_score(attachments)
    total = min(100.0, class_part + keyword_part + url_part + attach_part)
    return RiskBreakdown(
        classification=round(class_part, 2),
        keywords=round(keyword_part, 2),
        urls=round(url_part, 2),
        attachments=round(attach_part, 2),
        total=round(total, 2),
    )


def threat_level_for(risk: float) -> str:
    """Map a 0-100 risk score to a threat level label."""
    if risk >= settings.risk_thresholds_critical:
        return "critical"
    if risk >= settings.risk_thresholds_high:
        return "high"
    if risk >= settings.risk_thresholds_medium:
        return "medium"
    return "low"