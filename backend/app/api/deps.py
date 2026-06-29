"""Authentication / authorization dependencies (FastAPI)."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header
from firebase_admin import auth as firebase_auth
from jose import JWTError
from sqlalchemy.orm import Session

from app.api.errors import ForbiddenError, UnauthorizedError
from app.core.constants import UserRole
from app.core.security import decode_access_token
from app.database.connection import get_db
from app.models.user import User
from app.services import firebase_auth_service, user_service


def _extract_bearer(authorization: str | None) -> str:
    if not authorization:
        raise UnauthorizedError("Missing Authorization header")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise UnauthorizedError("Invalid Authorization header format")
    return parts[1]


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
) -> User:
    """Resolve the JWT in `Authorization: Bearer <token>` to a User row."""
    token = _extract_bearer(authorization)
    try:
        payload = decode_access_token(token)
    except JWTError as exc:
        raise UnauthorizedError(f"Invalid token: {exc}") from exc

    sub = payload.get("sub")
    if sub is None:
        raise UnauthorizedError("Token missing subject")
    try:
        user_id = int(sub)
    except (TypeError, ValueError) as exc:
        raise UnauthorizedError("Invalid subject in token") from exc

    user = user_service.get_by_id(db, user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("User not found or inactive")
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Require an admin role."""
    if current_user.role != UserRole.ADMIN:
        raise ForbiddenError("Admin privileges required")
    return current_user


async def get_firebase_user(
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
) -> User:
    """Resolve a Firebase ID token (Authorization: Bearer <ID_TOKEN>) to a User.

    Upserts the user into MySQL on first sign-in using Firebase claims.
    """
    token = _extract_bearer(authorization)
    try:
        claims = await firebase_auth_service.verify_id_token(token)
    except firebase_auth.ExpiredIdTokenError as exc:
        raise UnauthorizedError("Firebase ID token has expired") from exc
    except firebase_auth.RevokedIdTokenError as exc:
        raise UnauthorizedError("Firebase ID token has been revoked") from exc
    except firebase_auth.InvalidIdTokenError as exc:
        raise UnauthorizedError(f"Invalid Firebase ID token: {exc}") from exc
    except Exception as exc:
        raise UnauthorizedError(f"Firebase verification failed: {exc}") from exc

    user = await _resolve_firebase_user(db, claims)
    return user


async def _resolve_firebase_user(db: Session, claims: dict) -> User:
    """Find the user by firebase_uid, upsert if first time, link by email otherwise."""
    firebase_uid: str = claims["uid"]
    email: str | None = claims.get("email")
    name: str | None = claims.get("name")
    picture: str | None = claims.get("picture")

    user = user_service.get_by_firebase_uid(db, firebase_uid)
    if user is not None:
        # Refresh profile fields opportunistically.
        updated = False
        if name and user.full_name != name:
            user.full_name = name
            updated = True
        if picture and user.avatar_url != picture:
            user.avatar_url = picture
            updated = True
        if not user.is_verified and claims.get("email_verified"):
            user.is_verified = True
            updated = True
        if updated:
            db.commit()
            db.refresh(user)
        return user

    # Fallback: link by email if Firebase user already exists with local password.
    if email:
        user = user_service.get_by_email(db, email)
        if user is not None:
            user.firebase_uid = firebase_uid
            user.auth_provider = "google"
            if picture and not user.avatar_url:
                user.avatar_url = picture
            if not user.is_verified and claims.get("email_verified"):
                user.is_verified = True
            db.commit()
            db.refresh(user)
            return user

    user = user_service.create_firebase_user(
        db,
        firebase_uid=firebase_uid,
        email=email,
        full_name=name,
        avatar_url=picture,
        email_verified=bool(claims.get("email_verified")),
    )
    return user