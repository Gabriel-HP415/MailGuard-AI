"""Seed a few predictions via the live API and verify the dashboard
endpoints surface them correctly. Uses admin@mailguard.ai from seed.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8003/api/v1"


def login() -> str:
    req = urllib.request.Request(
        f"{BASE}/auth/login",
        method="POST",
        headers={"Content-Type": "application/json"},
        data=json.dumps({
            "email": "admin@mailguard.ai",
            "password": "ChangeMe123!",
        }).encode(),
    )
    return json.loads(urllib.request.urlopen(req, timeout=10).read())["access_token"]


def post(path: str, body: dict, token: str):
    req = urllib.request.Request(
        f"{BASE}{path}",
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        data=json.dumps(body).encode(),
    )
    try:
        return urllib.request.urlopen(req, timeout=30).read().decode()
    except urllib.error.HTTPError as e:
        return f"ERR {e.code}: {e.read().decode()[:300]}"


def get(path: str, token: str):
    req = urllib.request.Request(
        f"{BASE}{path}",
        headers={"Authorization": f"Bearer {token}"},
    )
    return urllib.request.urlopen(req, timeout=10).read().decode()


def main() -> int:
    tok = login()
    print(f"[ok] got token len={len(tok)}")

    for fname in [
        "scripts/_predict_payload.json",
        "scripts/_predict_normal.json",
        "scripts/_predict_spam.json",
    ]:
        body = json.loads(open(fname, encoding="utf-8").read())
        resp = post("/predictions", body, tok)
        if resp.startswith("ERR"):
            print(f"  [{fname}] FAIL: {resp}")
        else:
            d = json.loads(resp)
            print(f"  [{fname}] cls={d.get('predicted_class')} risk={d.get('risk_score'):.1f} threat={d.get('threat_level')}")

    print("\n[step] GET /dashboard/stats?days=30")
    print(get("/dashboard/stats?days=30", tok))

    print("\n[step] GET /dashboard/recent?limit=10")
    print(get("/dashboard/recent?limit=10", tok))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())