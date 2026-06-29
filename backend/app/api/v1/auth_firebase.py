"""Firebase Authentication endpoints for the Chrome extension.

The extension performs the actual Google OAuth dance via `chrome.identity`,
then sends the resulting Firebase ID token here. We verify it, upsert the
user, and issue our internal JWT so downstream endpoints keep working
unchanged.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Request
from firebase_admin import auth as firebase_admin_auth
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import _extract_bearer
from app.core.config import settings
from app.core.security import create_access_token
from app.database.connection import get_db
from app.models.user import User
from app.schemas.auth import TokenResponse, UserResponse
from app.services import activity_log_service, firebase_auth_service, user_service

router = APIRouter()


class FirebaseLoginRequest(BaseModel):
    """Body sent by the Chrome extension after `signInWithGoogle`."""

    id_token: str = Field(min_length=10, description="Firebase ID token from chrome.identity flow")


@router.post("/login", response_model=TokenResponse)
async def firebase_login(
    payload: FirebaseLoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Verify a Firebase ID token, upsert the user, return our internal JWT."""
    try:
        claims = await firebase_auth_service.verify_id_token(payload.id_token)
    except firebase_admin_auth.ExpiredIdTokenError as exc:
        from app.api.errors import UnauthorizedError

        raise UnauthorizedError("Firebase ID token has expired") from exc
    except firebase_admin_auth.RevokedIdTokenError as exc:
        from app.api.errors import UnauthorizedError

        raise UnauthorizedError("Firebase ID token has been revoked") from exc
    except firebase_admin_auth.InvalidIdTokenError as exc:
        from app.api.errors import UnauthorizedError

        raise UnauthorizedError(f"Invalid Firebase ID token: {exc}") from exc
    except Exception as exc:
        from app.api.errors import UnauthorizedError

        raise UnauthorizedError(f"Firebase verification failed: {exc}") from exc

    firebase_uid: str = claims["uid"]
    email: str | None = claims.get("email")
    name: str | None = claims.get("name")
    picture: str | None = claims.get("picture")

    user = user_service.get_by_firebase_uid(db, firebase_uid)
    if user is None and email:
        user = user_service.get_by_email(db, email)

    if user is None:
        user = user_service.create_firebase_user(
            db,
            firebase_uid=firebase_uid,
            email=email,
            full_name=name,
            avatar_url=picture,
            email_verified=bool(claims.get("email_verified")),
        )
    else:
        if user.firebase_uid is None:
            user.firebase_uid = firebase_uid
        if user.auth_provider != "google":
            user.auth_provider = "google"
        if name and user.full_name != name:
            user.full_name = name
        if picture and user.avatar_url != picture:
            user.avatar_url = picture
        if not user.is_verified and claims.get("email_verified"):
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
            "auth_provider": user.auth_provider or "google",
        },
    )

    activity_log_service.log(
        db,
        user=user,
        action="firebase_login",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.get("/status", response_model=dict)
async def firebase_status():
    """Report whether the backend can verify Firebase tokens."""
    return {
        "enabled": settings.firebase_enabled,
        "project_id": settings.firebase_project_id,
        "initialized": firebase_auth_service.is_initialized(),
    }