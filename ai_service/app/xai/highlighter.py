"""Highlight suspicious spans in the email body."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ai_service.app.constants import KEYWORD_WEIGHTS, URL_SHORTENERS
from ai_service.app.preprocessing.url_extractor import analyze_url, extract_links


@dataclass
class HighlightedSpan:
    """A contiguous suspicious region in the email text."""

    start: int
    end: int
    text: str
    category: str  # keyword | url | threat
    weight: float
    reason: str


def find_keyword_spans(text: str) -> list[HighlightedSpan]:
    """Return spans where known suspicious keywords appear."""
    if not text:
        return []
    spans: list[HighlightedSpan] = []
    text_l = text.lower()
    for phrase, weight in KEYWORD_WEIGHTS.items():
        start = 0
        while True:
            i = text_l.find(phrase, start)
            if i < 0:
                break
            spans.append(
                HighlightedSpan(
                    start=i,
                    end=i + len(phrase),
                    text=text[i : i + len(phrase)],
                    category="keyword",
                    weight=weight,
                    reason=f"Suspicious phrase: '{phrase}'",
                )
            )
            start = i + len(phrase)
    return spans


def find_url_spans(text: str) -> list[HighlightedSpan]:
    """Return spans for risky URLs."""
    spans: list[HighlightedSpan] = []
    for url in extract_links(text or ""):
        analysis = analyze_url(url)
        i = (text or "").find(url)
        if i < 0:
            continue
        spans.append(
            HighlightedSpan(
                start=i,
                end=i + len(url),
                text=url,
                category="url",
                weight=analysis.risk_score,
                reason="; ".join(analysis.reasons) or "Suspicious URL",
            )
        )
    return spans


def build_highlighted_spans(
    text: str,
    *,
    keywords: bool = True,
    urls: bool = True,
) -> list[dict]:
    """Return a list of dict spans ready to be stored in JSON."""
    spans: list[HighlightedSpan] = []
    if keywords:
        spans.extend(find_keyword_spans(text))
    if urls:
        spans.extend(find_url_spans(text))
    # Merge overlapping spans (e.g. URL containing a keyword).
    spans.sort(key=lambda s: (s.start, -s.end))
    merged: list[HighlightedSpan] = []
    for s in spans:
        if merged and s.start <= merged[-1].end:
            prev = merged[-1]
            new_end = max(prev.end, s.end)
            new_weight = max(prev.weight, s.weight)
            merged[-1] = HighlightedSpan(
                start=prev.start,
                end=new_end,
                text=prev.text,  # keep first text
                category=prev.category,
                weight=new_weight,
                reason=f"{prev.reason}; {s.reason}",
            )
        else:
            merged.append(s)
    return [
        {
            "start": s.start,
            "end": s.end,
            "text": s.text,
            "category": s.category,
            "weight": s.weight,
            "reason": s.reason,
        }
        for s in merged
    ]