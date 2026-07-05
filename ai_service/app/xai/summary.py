"""Build human-readable explanation summaries from risk components."""

from __future__ import annotations

from typing import Iterable

from ai_service.app.constants import EmailClass
from ai_service.app.risk.scorer import RiskBreakdown


_LABEL_DESCRIPTIONS = {
    EmailClass.NORMAL.value: "This email appears to be a normal message.",
    EmailClass.NOTIFICATION.value: "This is a routine notification email.",
    EmailClass.SPAM.value: "This email shows characteristics of unsolicited spam.",
    EmailClass.SCAM.value: "This email shows characteristics of a scam or phishing attempt.",
}


def build_explanation_summary(
    *,
    predicted_class: str,
    confidence: float,
    risk: RiskBreakdown,
    top_keyword_hits: Iterable[dict] | None = None,
    top_url_hits: Iterable[dict] | None = None,
) -> dict:
    """Construct a JSON-serializable explanation of the prediction."""
    summary_lines: list[str] = []
    summary_lines.append(
        _LABEL_DESCRIPTIONS.get(
            predicted_class, f"Predicted class: {predicted_class}"
        )
    )
    summary_lines.append(
        f"Model confidence: {confidence * 100:.1f}%."
    )
    summary_lines.append(
        f"Overall risk score: {risk.total:.1f}/100 "
        f"(class {risk.classification:.0f} + keywords {risk.keywords:.0f}"
        f" + URLs {risk.urls:.0f} + attachments {risk.attachments:.0f})."
    )
    if top_keyword_hits:
        keywords = sorted(top_keyword_hits, key=lambda x: -x.get("weight", 0))[:5]
        joined = ", ".join(f"'{k['keyword']}'" for k in keywords)
        summary_lines.append(f"Top suspicious phrases: {joined}.")
    if top_url_hits:
        urls = sorted(top_url_hits, key=lambda x: -x.get("weight", 0))[:3]
        joined = ", ".join(u.get("text", u.get("url", "")) for u in urls)
        summary_lines.append(f"Risky URLs detected: {joined}.")
    if risk.urls >= 20:
        summary_lines.append("URL analysis indicates elevated phishing risk.")
    if risk.classification >= 50:
        summary_lines.append("The classifier is highly confident this is malicious.")

    return {
        "summary": " ".join(summary_lines),
        "lines": summary_lines,
        "components": {
            "classification": risk.classification,
            "keywords": risk.keywords,
            "urls": risk.urls,
            "attachments": risk.attachments,
            "total": risk.total,
        },
    }