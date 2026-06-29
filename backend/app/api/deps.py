"""Authentication / authorization dependencies (FastAPI)."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header
from jose import JWTError
from sqlalchemy.orm import Session

from app.api.errors import ForbiddenError, UnauthorizedError
from app.core.constants import UserRole
from app.core.security import decode_access_token
from app.database.connection import get_db
from app.models.user import User
from app.services import user_service


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