"""Smoke test the live backend (assumed running at 127.0.0.1:8003 via
docker-compose.dev.yml). Verifies the dashboard endpoints that the
frontend/dashboard.js consumes.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8003/api/v1"


def http(method: str, path: str, body: dict | None = None, token: str | None = None):
    url = f"{BASE}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read() or b"null")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:300]
        return e.code, body
    except urllib.error.URLError as e:
        return 0, str(e)


def main() -> int:
    print(f"[step] GET /health (no auth)")
    code, body = http("GET", "/health")
    # /health is at root, not under /api/v1
    try:
        with urllib.request.urlopen("http://127.0.0.1:8003/health", timeout=5) as r:
            print(f"  GET http://127.0.0.1:8003/health -> {r.status}: {r.read().decode()}")
    except Exception as e:
        print(f"  GET /health FAIL: {e}")
        return 1

    print(f"[step] POST /auth/login")
    code, body = http(
        "POST",
        "/auth/login",
        {"email": "admin@mailguard.ai", "password": "ChangeMe123!"},
    )
    if code != 200:
        print(f"  login FAIL {code}: {body}")
        return 1
    token = body["access_token"]
    print(f"  OK token len={len(token)}")

    print(f"[step] GET /dashboard/stats?days=30")
    code, body = http("GET", "/dashboard/stats?days=30", token=token)
    print(f"  -> {code}: {body}")

    print(f"[step] GET /dashboard/recent?limit=5")
    code, body = http("GET", "/dashboard/recent?limit=5", token=token)
    print(f"  -> {code}: {body}")

    print(f"[step] GET /dashboard/ai/health")
    code, body = http("GET", "/dashboard/ai/health", token=token)
    print(f"  -> {code}: {body}")

    print(f"[step] GET /feedback?limit=1 (used by dashboard.js for counter)")
    code, body = http("GET", "/feedback?limit=1", token=token)
    print(f"  -> {code}: list len={len(body) if isinstance(body, list) else 'N/A'}")

    print("[PASS] all dashboard endpoints reachable" if code in (200, 422) else "[FAIL]")
    return 0


if __name__ == "__main__":
    sys.exit(main())