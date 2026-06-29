"""Text cleaning & normalization utilities."""

from __future__ import annotations

import html
import re
import unicodedata
from email.utils import parseaddr

# Compiled regexes for performance.
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_STYLE_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_URL_RE = re.compile(r"https?://[^\s<>\"']+|www\.[^\s<>\"']+", re.IGNORECASE)
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
_WS_RE = re.compile(r"\s+")
_NON_PRINTABLE_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def strip_html(html_text: str) -> str:
    """Strip HTML tags and decode entities, removing script/style content."""
    if not html_text:
        return ""
    no_script = _SCRIPT_STYLE_RE.sub(" ", html_text)
    no_tags = _HTML_TAG_RE.sub(" ", no_script)
    decoded = html.unescape(no_tags)
    return decoded


def clean_text(text: str, *, max_length: int = 5000) -> str:
    """Normalize an email's body text.

    - Decode HTML entities / strip tags.
    - Replace URLs and emails with placeholders.
    - Normalize Unicode, lowercase, collapse whitespace.
    """
    if not text:
        return ""
    if "<" in text and ">" in text:
        text = strip_html(text)
    text = _URL_RE.sub(" URLTOKEN ", text)
    text = _EMAIL_RE.sub(" EMAILTOKEN ", text)
    text = html.unescape(text)
    text = unicodedata.normalize("NFKC", text)
    text = _NON_PRINTABLE_RE.sub("", text)
    text = text.lower()
    text = _WS_RE.sub(" ", text).strip()
    if max_length and len(text) > max_length:
        text = text[:max_length]
    return text


def normalize_email(
    subject: str | None = None,
    body: str | None = None,
    sender: str | None = None,
) -> str:
    """Build a single normalized string used as model input."""
    parts: list[str] = []
    if subject:
        parts.append(f"subject: {clean_text(subject)}")
    if body:
        parts.append(f"body: {clean_text(body)}")
    if sender:
        name, addr = parseaddr(sender)
        domain = addr.split("@", 1)[-1] if "@" in addr else ""
        parts.append(f"from: {clean_text(name) or clean_text(addr)} domain: {domain.lower()}")
    return " ".join(parts).strip()


def extract_sender_domain(sender: str | None) -> str | None:
    """Extract the domain part of an email sender."""
    if not sender:
        return None
    _, addr = parseaddr(sender)
    if "@" in addr:
        return addr.split("@", 1)[-1].lower()
    return None