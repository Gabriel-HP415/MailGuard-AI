# MailGuard-AI — Healthcheck & smoke test
#
# Usage:
#   python scripts/health_check.py
#
# Exits non-zero on any failure. Designed to be run from cron / monitoring
# after `docker compose up`.

from __future__ import annotations

import argparse
import json
import logging
import sys
import urllib.request
from urllib.error import HTTPError, URLError

logger = logging.getLogger("healthcheck")


def _check(name: str, url: str, expected_status: int = 200) -> bool:
    logger.info("→ %s (%s)", name, url)
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            payload = resp.read()
            status = resp.status
            logger.info("  status=%d, bytes=%d", status, len(payload))
            if status == expected_status:
                try:
                    logger.info("  body=%s", json.loads(payload))
                except Exception:
                    logger.info("  body=(non-JSON)")
                return True
            return False
    except HTTPError as exc:
        logger.error("  HTTP error: %s", exc)
        return False
    except URLError as exc:
        logger.error("  unreachable: %s", exc)
        return False
    except Exception as exc:  # noqa: BLE001
        logger.error("  unexpected: %s", exc)
        return False


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    p = argparse.ArgumentParser(description="MailGuard-AI smoke test")
    p.add_argument("--backend",  default="http://localhost:8000", help="Backend base URL")
    p.add_argument("--ai",       default="http://localhost:8001", help="AI service base URL")
    p.add_argument("--frontend", default="http://localhost:8080", help="Frontend base URL")
    args = p.parse_args()

    checks = [
        ("Backend health",  f"{args.backend}/health"),
        ("Backend docs",    f"{args.backend}/docs"),
        ("Backend API v1",  f"{args.backend}/api/v1/auth/me"),
        ("AI health",       f"{args.ai}/health"),
        ("AI docs",         f"{args.ai}/docs"),
        ("Frontend root",   args.frontend),
    ]

    failures = 0
    for name, url in checks:
        if not _check(name, url):
            failures += 1

    if failures:
        logger.error("✗ %d / %d checks failed", failures, len(checks))
        return 1
    logger.info("✓ All %d checks passed", len(checks))
    return 0


if __name__ == "__main__":
    sys.exit(main())