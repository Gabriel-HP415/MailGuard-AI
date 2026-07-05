"""End-to-end smoke test for MailGuard-AI backend.

Hits each public + private endpoint with real HTTP requests against
http://127.0.0.1:8003 and prints a green check on pass / red cross on fail.

Usage (host or container):
    python scripts/smoke_test.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any

import httpx

BASE = os.environ.get("MG_BASE_URL", "http://127.0.0.1:8003")
TIMEOUT = 10.0

# Track overall result
results: list[tuple[str, str, bool, str]] = []  # (endpoint, method, ok, detail)


def _check(name: str, method: str, ok: bool, detail: str = "") -> None:
    mark = "OK " if ok else "FAIL"
    results.append((name, method, ok, detail))
    print(f"  [{mark}] {method:6s} {name:50s} {detail}".rstrip())


def main() -> int:
    print(f"== MailGuard-AI smoke test against {BASE} ==\n")

    with httpx.Client(timeout=TIMEOUT) as c:
        # ----- Public -----
        print("Public:")
        try:
            r = c.get(f"{BASE}/api/v1/health")
            _check("/api/v1/health", "GET", r.status_code == 200,
                   f"{r.status_code} | {r.json().get('status', '?')}")
        except Exception as e:
            _check("/api/v1/health", "GET", False, repr(e))

        try:
            r = c.get(f"{BASE}/docs")
            _check("/docs (Swagger)", "GET", r.status_code == 200, str(r.status_code))
        except Exception as e:
            _check("/docs", "GET", False, repr(e))

        # ----- Auth flow -----
        print("\nAuth:")
        email = f"smoke_{int(time.time())}@test.dev"
        register_body = {
            "email": email,
            "username": f"smoke{int(time.time())}",
            "password": "Smoke1234!",
            "full_name": "Smoke Test",
        }
        r = c.post(f"{BASE}/api/v1/auth/register", json=register_body)
        register_ok = r.status_code == 201 and "access_token" in r.json()
        _check("/api/v1/auth/register", "POST", register_ok,
               f"{r.status_code} | {'token' if register_ok else r.text[:60]}")
        user_token = r.json().get("access_token") if register_ok else ""

        r = c.post(f"{BASE}/api/v1/auth/login",
                   json={"email": email, "password": "Smoke1234!"})
        login_ok = r.status_code == 200 and "access_token" in r.json()
        _check("/api/v1/auth/login", "POST", login_ok,
               f"{r.status_code} | {'token' if login_ok else r.text[:60]}")
        if not user_token:
            user_token = r.json().get("access_token", "")

        user_hdr = {"Authorization": f"Bearer {user_token}"}

        r = c.get(f"{BASE}/api/v1/auth/me", headers=user_hdr)
        _check("/api/v1/auth/me", "GET", r.status_code == 200,
               f"{r.status_code} | {r.json().get('email', '?')}")

        # Negative: login with wrong password
        r = c.post(f"{BASE}/api/v1/auth/login",
                   json={"email": email, "password": "WrongPass"})
        _check("/api/v1/auth/login (wrong pw -> 401)", "POST",
               r.status_code == 401, str(r.status_code))

        # Anonymous /me -> 401
        r = c.get(f"{BASE}/api/v1/auth/me")
        _check("/api/v1/auth/me (anon -> 401)", "GET",
               r.status_code == 401, str(r.status_code))

        # ----- Admin token -----
        # Login as seeded admin
        r = c.post(f"{BASE}/api/v1/auth/login",
                   json={"email": "admin@mailguard.ai",
                         "password": "ChangeMe123!"})
        admin_ok = r.status_code == 200
        _check("/api/v1/auth/login (admin)", "POST", admin_ok,
               f"{r.status_code} | {'token' if admin_ok else r.text[:60]}")
        admin_token = r.json().get("access_token", "") if admin_ok else ""
        admin_hdr = {"Authorization": f"Bearer {admin_token}"}

        # ----- Predictions -----
        print("\nPredictions:")
        email_body = {
            "subject": "URGENT: Verify your account now",
            "sender": "noreply@suspicious-site.tk",
            "sender_domain": "suspicious-site.tk",
            "recipient": "alice@test.dev",
            "body_text": "Click here immediately to avoid suspension: http://bit.ly/abc123",
            "links": ["http://bit.ly/abc123"],
        }
        r = c.post(f"{BASE}/api/v1/predictions", headers=user_hdr,
                   json={"email": email_body, "include_explanation": False})
        pred_ok = r.status_code == 201
        _check("/api/v1/predictions", "POST", pred_ok,
               f"{r.status_code} | {r.json().get('predicted_class', r.text[:60])}")
        prediction_id = r.json().get("id") if pred_ok else None

        r = c.get(f"{BASE}/api/v1/predictions", headers=user_hdr)
        _check("/api/v1/predictions list", "GET",
               r.status_code == 200,
               f"{r.status_code} | {len(r.json())} items")

        if prediction_id:
            r = c.get(f"{BASE}/api/v1/predictions/{prediction_id}",
                      headers=user_hdr)
            _check(f"/api/v1/predictions/{prediction_id}", "GET",
                   r.status_code == 200, str(r.status_code))

        # ----- Emails -----
        print("\nEmails:")
        r = c.post(f"{BASE}/api/v1/emails", headers=user_hdr, json=email_body)
        _check("/api/v1/emails", "POST", r.status_code == 201, str(r.status_code))

        r = c.get(f"{BASE}/api/v1/emails", headers=user_hdr)
        _check("/api/v1/emails list", "GET",
               r.status_code == 200,
               f"{r.status_code} | {len(r.json())} items")

        # ----- Whitelist / Blacklist -----
        print("\nLists (whitelist/blacklist):")
        wl_body = {"sender": "trusted@partner.com",
                   "domain": "partner.com",
                   "note": "Smoke test whitelist entry"}
        r = c.post(f"{BASE}/api/v1/lists/whitelist", headers=user_hdr,
                   json=wl_body)
        _check("/api/v1/lists/whitelist", "POST",
               r.status_code == 201,
               f"{r.status_code} | id={r.json().get('id', '?')}")
        wl_id = r.json().get("id") if r.status_code == 201 else None

        r = c.get(f"{BASE}/api/v1/lists/whitelist", headers=user_hdr)
        _check("/api/v1/lists/whitelist list", "GET",
               r.status_code == 200,
               f"{r.status_code} | {len(r.json())} items")

        bl_body = {"sender": "spam@evil.tk",
                   "domain": "evil.tk",
                   "reason": "Smoke test blacklist entry"}
        r = c.post(f"{BASE}/api/v1/lists/blacklist", headers=user_hdr,
                   json=bl_body)
        _check("/api/v1/lists/blacklist", "POST",
               r.status_code == 201,
               f"{r.status_code} | id={r.json().get('id', '?')}")

        r = c.get(f"{BASE}/api/v1/lists/blacklist", headers=user_hdr)
        _check("/api/v1/lists/blacklist list", "GET",
               r.status_code == 200,
               f"{r.status_code} | {len(r.json())} items")

        if wl_id:
            r = c.delete(f"{BASE}/api/v1/lists/whitelist/{wl_id}",
                         headers=user_hdr)
            _check(f"/api/v1/lists/whitelist/{wl_id}", "DELETE",
                   r.status_code == 204, str(r.status_code))

        # ----- Feedback -----
        print("\nFeedback:")
        if prediction_id:
            fb_body = {"prediction_id": prediction_id,
                       "is_correct": True,
                       "comment": "Smoke test feedback"}
            r = c.post(f"{BASE}/api/v1/feedback", headers=user_hdr,
                       json=fb_body)
            _check("/api/v1/feedback", "POST",
                   r.status_code == 201, str(r.status_code))

            r = c.get(f"{BASE}/api/v1/feedback", headers=user_hdr)
            _check("/api/v1/feedback list", "GET",
                   r.status_code == 200,
                   f"{r.status_code} | {len(r.json())} items")

        # ----- Dashboard -----
        print("\nDashboard:")
        r = c.get(f"{BASE}/api/v1/dashboard/stats", headers=user_hdr)
        _check("/api/v1/dashboard/stats", "GET",
               r.status_code == 200,
               f"{r.status_code} | keys={list(r.json().keys())[:4]}")

        r = c.get(f"{BASE}/api/v1/dashboard/recent", headers=user_hdr)
        _check("/api/v1/dashboard/recent", "GET",
               r.status_code == 200,
               f"{r.status_code} | {len(r.json())} items")

        r = c.get(f"{BASE}/api/v1/dashboard/ai/health")
        _check("/api/v1/dashboard/ai/health", "GET",
               r.status_code == 200,
               f"{r.status_code} | {r.json().get('status', '?')}")

        # ----- Admin (must be 200 for admin, 403 for user) -----
        print("\nAdmin (RBAC):")
        r = c.get(f"{BASE}/api/v1/admin/models", headers=user_hdr)
        _check("/api/v1/admin/models as USER", "GET",
               r.status_code == 403, f"{r.status_code} (expect 403)")

        r = c.get(f"{BASE}/api/v1/admin/models", headers=admin_hdr)
        _check("/api/v1/admin/models as ADMIN", "GET",
               r.status_code == 200,
               f"{r.status_code} | {len(r.json())} items")

    # ----- Summary -----
    print("\n" + "=" * 70)
    total = len(results)
    passed = sum(1 for _, _, ok, _ in results if ok)
    failed = total - passed
    print(f"PASS {passed}/{total}    FAIL {failed}/{total}")
    if failed:
        print("\nFailed:")
        for name, method, ok, detail in results:
            if not ok:
                print(f"  - {method:6s} {name:50s} {detail}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
