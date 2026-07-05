"""Tests for /api/v1/predictions.

Reference example for M1 (backend) team member: copy/adapt the
`regular_user`, `auth_headers`, and `client` fixtures from conftest.py
for each new test file. Aim for ≥ 60% branch coverage on the predictions
router by the end of Tier 2.
"""

from __future__ import annotations

from unittest.mock import patch


def test_predict_requires_auth(client):
    """Anonymous request to /predictions must return 401."""
    resp = client.post(
        "/api/v1/predictions",
        json={
            "email": {
                "subject": "Test",
                "sender": "test@example.com",
                "body_text": "Hello",
            }
        },
    )
    assert resp.status_code == 401


def test_predict_validation_error_on_short_body(client, auth_headers):
    """Empty subject fails Pydantic validation before reaching the AI."""
    resp = client.post(
        "/api/v1/predictions",
        headers=auth_headers,
        json={
            "email": {
                "subject": "",
                "sender": "test@example.com",
                "body_text": "Hi",
            }
        },
    )
    # Pydantic validation returns 422 (was 400 in v1; our wrapper normalises).
    assert resp.status_code in (400, 422)


def test_predict_returns_classification(client, auth_headers):
    """Happy path: submit a normal-looking email, get back a prediction."""
    # Stub out the AI service so the test doesn't depend on a real model.
    with patch("app.services.prediction_service.classify_email") as mock:
        mock.return_value = {
            "predicted_class": "legitimate",
            "class_index": 0,
            "confidence": 0.97,
            "risk_score": 5.0,
            "threat_level": "low",
            "suspicious_urls": [],
            "model_version": "stub-v1",
            "explanation": None,
        }
        resp = client.post(
            "/api/v1/predictions",
            headers=auth_headers,
            json={
                "email": {
                    "subject": "Project update",
                    "sender": "colleague@example.com",
                    "body_text": "Hi, just sharing the latest report.",
                },
                "include_explanation": False,
            },
        )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["predicted_class"] == "legitimate"
    assert body["risk_score"] == 5.0
    assert "id" in body


def test_list_predictions_paginated(client, auth_headers):
    """Pagination params should be respected."""
    resp = client.get(
        "/api/v1/predictions",
        headers=auth_headers,
        params={"limit": 5, "offset": 0},
    )
    assert resp.status_code == 200
    data = resp.json()
    # Empty list is acceptable; just make sure structure is right.
    assert "items" in data or isinstance(data, list)
