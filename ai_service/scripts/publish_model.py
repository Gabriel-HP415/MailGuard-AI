"""Publish a trained model version to the backend admin API.

Uses HTTP (no SQLAlchemy coupling) so the AI Service stays decoupled.

Modes:
- `--register-only`    POST /api/v1/admin/models           (just register)
- `--activate`         POST /api/v1/admin/models/{id}/activate  (also activate)
- `--description-...`  metadata string

Usage:
    python -m ai_service.scripts.publish_model \
        --version v1.0.1 \
        --algorithm distilbert \
        --accuracy 0.9741 \
        --artifact-path models/artifacts/distilbert-v1.0.1 \
        --description "Finetune 3 epochs on merged_dataset.csv" \
        --activate
"""

from __future__ import annotations

import argparse
import json
import logging
import urllib.request
from urllib.error import HTTPError

from ai_service.app.config import settings

logger = logging.getLogger(__name__)


def _http(method: str, url: str, *, body: dict | None = None, token: str | None = None) -> dict:
    data = json.dumps(body or {}).encode("utf-8")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data if body is not None else None,
                                 method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = resp.read()
            return json.loads(payload) if payload else {}
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"{method} {url} -> {exc.code}: {body}") from exc


def _admin_login(email: str, password: str) -> str:
    resp = _http(
        "POST",
        f"{settings.backend_url.rstrip('/')}/api/v1/auth/login",
        body={"email": email, "password": password},
    )
    return resp["access_token"]


def publish(
    *,
    version: str,
    algorithm: str,
    accuracy: float,
    artifact_path: str | None,
    description: str | None,
    backend_url: str | None,
    admin_email: str | None,
    admin_password: str | None,
    activate: bool,
    force: bool,
) -> dict:
    """Register a new model version (and optionally activate it).

    Returns the JSON response from the admin API.
    """
    base = (backend_url or settings.backend_url).rstrip("/") + "/api/v1/admin/models"
    token = _admin_login(admin_email, admin_password) if admin_email else None

    payload = {
        "version": version,
        "algorithm": algorithm,
        "accuracy": accuracy,
        "artifact_path": artifact_path,
        "description": description,
        "is_active": False,  # always create inactive; activation happens via PATCH or activate endpoint
    }

    try:
        registered = _http("POST", base, body=payload, token=token)
    except RuntimeError as exc:
        if "409" in str(exc) and force:
            logger.warning("Model version %s already exists; listing existing ones", version)
            existing = _http("GET", base, token=token)
            for mv in existing:
                if mv.get("version") == version:
                    registered = mv
                    break
            else:
                raise
        else:
            raise

    if activate and registered.get("id"):
        activate_url = f"{base}/{registered['id']}/activate"
        registered = _http("POST", activate_url, token=token)
        logger.info("Activated model %s (id=%s)", version, registered["id"])
    return registered


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Publish a model version to the backend")
    p.add_argument("--version", required=True)
    p.add_argument("--algorithm", required=True,
                   choices=["naive_bayes", "logistic_regression", "svm",
                            "random_forest", "distilbert"])
    p.add_argument("--accuracy", type=float, default=0.0)
    p.add_argument("--artifact-path", default=None)
    p.add_argument("--description", default=None)
    p.add_argument("--backend-url", default=None,
                   help="Defaults to settings.backend_url")
    p.add_argument("--admin-email", default=None,
                   help="If provided, will log in first to obtain an admin token")
    p.add_argument("--admin-password", default=None)
    p.add_argument("--activate", action="store_true")
    p.add_argument("--force", action="store_true",
                   help="If the version already exists, fetch & reuse it")
    args = p.parse_args()

    try:
        result = publish(
            version=args.version,
            algorithm=args.algorithm,
            accuracy=args.accuracy,
            artifact_path=args.artifact_path,
            description=args.description,
            backend_url=args.backend_url,
            admin_email=args.admin_email,
            admin_password=args.admin_password,
            activate=args.activate,
            force=args.force,
        )
    except RuntimeError as exc:
        logger.error("Failed to publish model: %s", exc)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())