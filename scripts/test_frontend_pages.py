"""Smoke test the frontend pages: spin up a static server, fetch each HTML
page and its referenced assets, and verify no 404s occur.

We don't run a real browser, but we replicate the network calls Chrome
would make and check that every resource the pages reference resolves.
"""
from __future__ import annotations

import http.server
import json
import socketserver
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "frontend"
PORT = 8765


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # silence access log

    def end_headers(self):
        # Serve .html with no-cache like nginx.conf does.
        super().end_headers()


def main() -> int:
    if not (ROOT / "index.html").exists():
        print(f"[FAIL] no frontend dir at {ROOT}")
        return 1

    os_chdir = ROOT
    handler = lambda *a, **kw: QuietHandler(*a, directory=str(os_chdir), **kw)
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    print(f"[OK] static server up on http://127.0.0.1:{PORT}")

    import urllib.request
    import re

    pages = ["index.html", "login.html", "dashboard.html", "predictions.html",
             "prediction.html", "lists.html", "admin.html", "register.html",
             "partials/navbar.html"]

    all_ok = True
    for page in pages:
        url = f"http://127.0.0.1:{PORT}/{page}"
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                body_bytes = r.read()
                status = r.status
            if status != 200:
                print(f"  [{page}] HTTP {status}")
                all_ok = False
                continue
            # Collect referenced asset URLs from the raw bytes
            text = body_bytes.decode("utf-8", errors="replace")
            css = re.findall(r'href="(assets/[^"]+)"', text)
            scripts = re.findall(r'src="(assets/[^"]+)"', text)
            for asset in css + scripts:
                with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/{asset}", timeout=5) as ar:
                    asset_bytes = ar.read()
                    size = len(asset_bytes)
                    if size < 100:
                        print(f"  [{page}] {asset} -> {size} bytes (TOO SMALL!)")
                        all_ok = False
                    else:
                        print(f"  [{page}] {asset} -> {size} bytes OK")
            # Also count the page's own size
            print(f"  [{page}] {len(body_bytes)} bytes OK")
        except Exception as e:
            print(f"  [{page}] FAIL: {e}")
            all_ok = False

    # Also explicitly test the three vendor files
    for vendor in [
        "assets/css/bootstrap.min.css",
        "assets/vendor/bootstrap.bundle.min.js",
        "assets/vendor/chart.umd.min.js",
    ]:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/{vendor}", timeout=5) as r:
                size = len(r.read())
                ok = size > 50_000
                print(f"  vendor {vendor}: {size} bytes {'OK' if ok else 'TOO SMALL'}")
                if not ok:
                    all_ok = False
        except Exception as e:
            print(f"  vendor {vendor}: FAIL ({e})")
            all_ok = False

    httpd.shutdown()
    if all_ok:
        print("\n[PASS] all frontend pages and vendor assets resolve")
        return 0
    print("\n[FAIL] some assets are missing")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())