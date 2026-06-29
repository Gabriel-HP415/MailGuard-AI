"""Firebase Admin SDK initialization and ID token verification.

Used by the Chrome extension sign-in flow. The extension exchanges an OAuth
authorization code for a Firebase ID token via the Identity Toolkit REST API,
then sends it to this backend on every request. We verify the token here and
upsert a MySQL row in the `users` table.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import firebase_admin
from firebase_admin import auth, credentials

logger = logging.getLogger(__name__)

_firebase_app: firebase_admin.App | None = None


def init_firebase(
    credentials_path: str,
    project_id: str,
    credentials_json: str | None = None,
) -> firebase_admin.App | None:
    """Initialize the Firebase Admin SDK once per process.

    Returns the App instance, or None when disabled / misconfigured so the
    backend can still boot in environments without Firebase (e.g. local dev
    against the legacy email/password flow).
    """
    global _firebase_app

    if _firebase_app is not None:
        return _firebase_app

    if not credentials_path and not credentials_json:
        logger.warning("Firebase credentials not configured — skipping init")
        return None

    try:
        if credentials_json:
            # Production / Render deployment path: JSON passed via env var.
            import json as _json

            info = _json.loads(credentials_json)
            cred = credentials.Certificate(info)
        else:
            abs_path = os.path.abspath(credentials_path)
            if not os.path.exists(abs_path):
                logger.warning(
                    "Firebase service account file not found at %s — Firebase auth disabled",
                    abs_path,
                )
                return None
            cred = credentials.Certificate(abs_path)

        _firebase_app = firebase_admin.initialize_app(
            cred,
            {"projectId": project_id} if project_id else None,
        )
        logger.info("Firebase Admin SDK initialized (project=%s)", project_id)
    except ValueError as exc:
        # Already initialized in this process (e.g. during tests).
        if "already exists" in str(exc):
            _firebase_app = firebase_admin.get_app()
        else:
            logger.exception("Failed to initialize Firebase Admin SDK: %s", exc)
            return None
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Unexpected Firebase init error: %s", exc)
        return None

    return _firebase_app


def is_initialized() -> bool:
    """Return True when the Firebase Admin app is ready."""
    return _firebase_app is not None or bool(firebase_admin._apps)


async def verify_id_token(id_token: str) -> dict[str, Any]:
    """Verify a Firebase ID token and return a dict of user claims.

    Raises firebase_admin.auth.InvalidIdTokenError / ExpiredIdTokenError /
    RevokedIdTokenError / CertificateFetchError when the token is bad.
    """
    if not is_initialized():
        raise RuntimeError(
            "Firebase Admin SDK is not initialized. "
            "Check firebase_credentials_path / firebase_project_id in .env"
        )

    decoded = auth.verify_id_token(id_token, check_revoked=True)
    return {
        "uid": decoded["uid"],
        "email": decoded.get("email"),
        "email_verified": decoded.get("email_verified", False),
        "name": decoded.get("name"),
        "picture": decoded.get("picture"),
        "iss": decoded.get("iss"),
        "aud": decoded.get("aud"),
        "auth_time": decoded.get("auth_time"),
        "exp": decoded.get("exp"),
    }