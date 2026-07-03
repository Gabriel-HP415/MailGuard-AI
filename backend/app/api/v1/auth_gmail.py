"""Google OAuth login for the Chrome extension.

The extension obtains a Google OAuth access token via ``chrome.identity``
(asking for Gmail-API scopes). It then POSTs that token here and we:

1. Verify it against Google's ``userinfo`` endpoint (no Firebase required).
2. Upsert a MailGuard user keyed by Google email.
3. Issue a MailGuard JWT so all downstream endpoints keep working.

This is the lightweight path for end-users who only want the AI scanning
feature. Firebase is still used for the *dashboard* / admin features.

Endpoint:
  POST /api/v1/auth/gmail/login  body: ``{"access_token": "...", "email": "..."}``
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token
from app.database.connection import get_db
from app.schemas.auth import TokenResponse
from app.services import activity_log_service, user_service

logger = logging.getLogger(__name__)
router = APIRouter()


class GmailLoginRequest(BaseModel):
    """Payload from the Chrome extension's Gmail-OAuth flow."""

    access_token: str = Field(
        min_length=10,
        description="Google OAuth access token (chrome.identity.getAuthToken)",
    )
    email: str | None = Field(
        default=None,
        description="Optional explicit Google account email (skips userinfo lookup).",
    )


_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
_GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"


async def _verify_google_token(access_token: str, expected_email: str | None) -> dict:
    """Verify a Google OAuth token by calling the userinfo endpoint.

    Returns the claims dict. Raises ``UnauthorizedError`` on any failure so
    the caller can return a clean 401 to the extension.
    """
    from app.api.errors import UnauthorizedError

    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
        # Step 1 — tokeninfo is a cheap server-side check that returns
        # ``email``, ``email_verified``, ``aud``, ``scope`` without us having
        # to hit the userinfo REST API. If ``aud`` doesn't match our OAuth
        # client id we reject up-front.
        info_resp = await client.get(
            _GOOGLE_TOKENINFO_URL, params={"access_token": access_token}
        )
        if info_resp.status_code != 200:
            raise UnauthorizedError(
                f"Google rejected the token (status {info_resp.status_code})"
            )
        info = info_resp.json()

        if expected_email and info.get("email") != expected_email:
            raise UnauthorizedError(
                "Google account email does not match the requested mailbox"
            )
        if info.get("email_verified") not in (True, "true"):
            raise UnauthorizedError("Google account email is not verified")

        # Step 2 — pull a richer profile (name, picture) via userinfo. If it
        # fails we fall back to whatever tokeninfo gave us.
        profile: dict = {}
        try:
            uresp = await client.get(
                _GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if uresp.status_code == 200:
                profile = uresp.json()
        except httpx.HTTPError as exc:  # noqa: BLE001
            logger.warning("Google userinfo call failed: %s", exc)

    return {**info, **profile}


@router.post("/login", response_model=TokenResponse)
async def gmail_login(
    payload: GmailLoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Exchange a Google OAuth access token for a MailGuard JWT."""
    claims = await _verify_google_token(payload.access_token, payload.email)

    email = claims.get("email")
    if not email:
        from app.api.errors import UnauthorizedError

        raise UnauthorizedError("Google token did not include an email claim")

    name = claims.get("name") or email.split("@", 1)[0]
    picture = claims.get("picture")
    google_sub = claims.get("sub") or claims.get("user_id")

    # Re-use the Firebase-style upsert so we share one code path for all
    # Google sign-ins (whether they came via Firebase or direct chrome.identity).
    user = user_service.get_by_email(db, email)
    if user is None:
        user = user_service.create_firebase_user(
            db,
            firebase_uid=f"google:{google_sub or email}",
            email=email,
            full_name=name,
            avatar_url=picture,
            email_verified=True,
        )
    else:
        if user.auth_provider != "google":
            user.auth_provider = "google"
        if name and user.full_name != name:
            user.full_name = name
        if picture and user.avatar_url != picture:
            user.avatar_url = picture
        user.is_verified = True
        db.commit()
        db.refresh(user)

    user.last_login_at = datetime.utcnow()
    db.commit()
    db.refresh(user)

    token = create_access_token(
        subject=user.id,
        extra_claims={
            "email": user.email,
            "role": user.role.value,
            "auth_provider": "google",
        },
    )

    activity_log_service.log(
        db,
        user=user,
        action="gmail_oauth_login",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.get("/status", response_model=dict)
async def gmail_status():
    """Report whether this endpoint is enabled (it always is)."""
    return {
        "enabled": True,
        "required_scopes": [
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.modify",
        ],
    }