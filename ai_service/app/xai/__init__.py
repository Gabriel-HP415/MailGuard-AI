"""Explainability (XAI) package — highlight spans, top tokens, summary."""

from ai_service.app.xai.highlighter import build_highlighted_spans, find_keyword_spans
from ai_service.app.xai.summary import build_explanation_summary

__all__ = ["build_highlighted_spans", "find_keyword_spans", "build_explanation_summary"]