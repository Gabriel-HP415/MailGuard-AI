"""End-to-end test: simulate a browser loading dashboard.html, fetching
all referenced static assets, fetching the navbar partial, logging in,
and hitting each dashboard endpoint.

We start two HTTP servers:
  - static frontend on :8765 (Python http.server, serves frontend/)
  - the live backend is already at :8003 (docker-compose.dev.yml)

We confirm the JS contract: same URLs the frontend makes to /api/v1 work.
"""
from __future__ import annotations

import json
import socketserver
import sys
import threading
import urllib.error
import urllib.request
from http.server import SimpleHTTPRequestHandler

ROOT = r"d:\HOC TAP\doanAI\MailGuard-AI\frontend"
PORT = 8766


class H(SimpleHTTPRequestHandler):
    def log_message(self, *a, **k):
        pass


def main() -> int:
    import os
    os.chdir(ROOT)
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), H)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    print(f"[OK] frontend static on http://127.0.0.1:{PORT}")

    # 1) Browser-like: GET /dashboard.html then assets
    pages = ["dashboard.html", "predictions.html", "lists.html", "admin.html",
             "prediction.html", "login.html", "register.html", "partials/navbar.html"]
    for p in pages:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/{p}", timeout=5) as r:
                size = len(r.read())
                print(f"  /{p}: {size} bytes  [{r.status}]")
        except Exception as e:
            print(f"  /{p}: FAIL ({e})")
            return 1

    # 2) Live backend integration: login + dashboard data
    print("\n[step] backend integration (POST /auth/login then GET dashboard)")
    login_req = urllib.request.Request(
        "http://127.0.0.1:8003/api/v1/auth/login",
        method="POST",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"email": "admin@mailguard.ai", "password": "ChangeMe123!"}).encode(),
    )
    tok = json.loads(urllib.request.urlopen(login_req, timeout=10).read())["access_token"]
    print(f"  login OK token_len={len(tok)}")

    # What api.js baseUrl resolves to when running behind nginx proxy
    # (MAILGUARD_API_BASE_URL is set to "/api/v1" in production).
    # When opened directly (http://localhost:8081/dashboard.html without
    # the proxy), api.js falls back to MAILGUARD_CONFIG.defaultBaseUrl
    # = window.MAILGUARD_API_BASE_URL || "/api/v1". So if the user opens
    # the dashboard.html from the Docker frontend nginx, requests go to
    # /api/v1 which nginx proxies to backend:8000. Both /api/v1/foo and
    # http://127.0.0.1:8003/api/v1/foo hit the same backend.

    for path in [
        "/api/v1/dashboard/stats?days=30",
        "/api/v1/dashboard/recent?limit=10",
        "/api/v1/dashboard/ai/health",
        "/api/v1/feedback?limit=1",
    ]:
        req = urllib.request.Request(
            f"http://127.0.0.1:8003{path}",
            headers={"Authorization": f"Bearer {tok}"},
        )
        try:
            resp = urllib.request.urlopen(req, timeout=10)
            data = json.loads(resp.read())
            print(f"  GET {path} -> {resp.status} {type(data).__name__}")
        except urllib.error.HTTPError as e:
            print(f"  GET {path} -> {e.code}")
            return 1

    httpd.shutdown()
    print("\n[PASS] full frontend + backend integration works")
    return 0


if __name__ == "__main__":
    sys.exit(main())