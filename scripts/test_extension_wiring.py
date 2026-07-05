"""Simulate what the Chrome extension does on first run.

When the extension loads:
  1. Reads `mg_base_url` from chrome.storage.local
  2. Falls back to DEFAULT_BASE_URL (the production Render URL)
  3. Tries to fetch /api/v1/health to confirm reachability

This script does exactly that, then prints the result so you can
verify "would the extension reach the dev backend?" before opening
Chrome at all.

Run from the project root:
    docker compose -f docker-compose.dev.yml exec backend python /tmp/test_extension_wiring.py
"""

from __future__ import annotations

import json
import sys
import httpx

# Same default the extension uses. We override via env so this script can
# simulate "user set it to a wrong URL".
PROD_BASE = "https://mailguard-ai-y0nh.onrender.com/api/v1"
LOCAL_BASE = "http://localhost:8000/api/v1"   # in-container name resolves to same
HOST_BASE_8003 = "http://127.0.0.1:8003/api/v1"


def probe(label: str, base: str) -> bool:
    try:
        r = httpx.get(f"{base}/health", timeout=5.0)
        data = r.json()
        ok = r.status_code == 200 and data.get("status") == "ok"
        mark = "OK " if ok else "FAIL"
        print(f"  [{mark}] {label:30s} {base:60s} -> {r.status_code} {data}")
        return ok
    except Exception as e:
        print(f"  [FAIL] {label:30s} {base:60s} -> {type(e).__name__}: {e}")
        return False


def main() -> int:
    print("== Extension wiring probe ==\n")
    print("Probe 1: Production Render URL (what would load if mg_base_url unset):")
    probe("Render (prod)", PROD_BASE)

    print("\nProbe 2: Local backend in this container (port 8000 in-container):")
    probe("Container localhost:8000", LOCAL_BASE)

    print("\nProbe 3: Local backend as seen from host (port 8003):")
    probe("Host 127.0.0.1:8003", HOST_BASE_8003)

    print("\n== Instructions ==")
    print("In Chrome, after loading the extension unpacked:")
    print("  1. Click the MailGuard icon in the toolbar")
    print("  2. If popup shows 'Disconnected', click '⚙ Open Settings'")
    print("  3. In Settings, set Backend URL = http://127.0.0.1:8003/api/v1")
    print("  4. Email = demo@localhost.dev   Password = Demo1234!")
    print("  5. Click 'Sign in'")
    print("  6. Open https://mail.google.com → extension should populate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
