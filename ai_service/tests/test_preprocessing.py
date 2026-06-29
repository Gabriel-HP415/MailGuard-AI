"""Tests for the AI Service — text cleaning, URL analysis, risk scoring,
and the merge_datasets fallback synthetic generators."""

from ai_service.app.preprocessing.text_cleaner import clean_text, extract_sender_domain, normalize_email
from ai_service.app.preprocessing.url_extractor import analyze_url, extract_links
from ai_service.app.risk.scorer import compute_risk, threat_level_for
from ai_service.scripts.merge_datasets import (
    _iter_synthetic_normal,
    _iter_synthetic_notifications,
    _parse_enron_message,
)


def test_clean_text_lowercases_and_strips_html():
    html = "<p>Hello <b>WORLD</b> https://example.com</p>"
    out = clean_text(html)
    assert "hello" in out
    assert "world" in out
    assert "URLTOKEN" in out
    assert "<" not in out and ">" not in out


def test_normalize_email_includes_subject_body_sender():
    s = normalize_email(
        subject="Hi",
        body="Just checking in",
        sender="Alice <alice@example.com>",
    )
    assert "subject: hi" in s
    assert "body: just checking in" in s
    assert "from: alice" in s
    assert "domain: example.com" in s


def test_extract_sender_domain():
    assert extract_sender_domain("Alice <alice@Example.COM>") == "example.com"
    assert extract_sender_domain("bob@gmail.com") == "gmail.com"
    assert extract_sender_domain(None) is None


def test_extract_links_returns_unique_urls():
    text = "Check http://bit.ly/abc and https://example.com"
    links = extract_links(text)
    assert "http://bit.ly/abc" in links
    assert any("example.com" in l for l in links)


def test_analyze_url_flags_shortener():
    a = analyze_url("http://bit.ly/abc")
    assert a.is_shortener is True
    assert a.risk_score > 0
    assert any("shortener" in r.lower() for r in a.reasons)


def test_compute_risk_high_for_scam_with_keywords():
    risk = compute_risk(
        predicted_class="scam",
        confidence=0.9,
        text="Verify your account immediately and click here to claim your prize",
        links=["http://bit.ly/x"],
    )
    assert risk.total > 50
    assert threat_level_for(risk.total) in {"high", "critical"}


def test_compute_risk_low_for_normal_email():
    risk = compute_risk(
        predicted_class="normal",
        confidence=0.9,
        text="Lunch on Friday?",
        links=[],
    )
    assert risk.total < 25
    assert threat_level_for(risk.total) == "low"


# ---- merge_datasets helpers ----

def test_parse_enron_message_extracts_subject_and_body():
    raw = (
        "Message-ID: <1@x>\n"
        "Date: Mon, 1 Jan 2024\n"
        "From: alice@example.com\n"
        "To: bob@example.com\n"
        "Subject: Lunch?\n"
        "\n"
        "Hey Bob, are we still on for lunch?\n"
    )
    subject, body = _parse_enron_message(raw)
    assert subject == "Lunch?"
    assert "are we still on" in body


def test_synthetic_generators_have_labels():
    normals = list(_iter_synthetic_normal(5))
    notifications = list(_iter_synthetic_notifications(5))
    assert len(normals) == 5
    assert len(notifications) == 5
    assert all(s.label == "normal" for s in normals)
    assert all(s.label == "notification" for s in notifications)
    assert all(s.subject for s in normals + notifications)
    assert all(s.body for s in normals + notifications)
    assert all(s.source for s in normals + notifications)