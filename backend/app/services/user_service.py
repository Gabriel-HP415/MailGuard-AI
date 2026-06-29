"""User service: create, authenticate, fetch."""

from __future__ import annotations

import re
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.errors import BadRequestError, ConflictError, UnauthorizedError
from app.core.constants import UserRole
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest


def get_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.get(User, user_id)


def get_by_email(db: Session, email: str) -> Optional[User]:
    return db.scalar(select(User).where(User.email == email))


def get_by_username(db: Session, username: str) -> Optional[User]:
    return db.scalar(select(User).where(User.username == username))


def get_by_firebase_uid(db: Session, firebase_uid: str) -> Optional[User]:
    return db.scalar(select(User).where(User.firebase_uid == firebase_uid))


def _derive_username(email: str | None, firebase_uid: str) -> str:
    """Generate a unique username from an email or fallback to firebase UID."""
    if email:
        candidate = re.split(r"@", email, maxsplit=1)[0]
        candidate = re.sub(r"[^a-zA-Z0-9._-]", "_", candidate).strip("._-")
        if candidate and len(candidate) >= 3:
            return candidate[:100]
    return f"user_{firebase_uid[:20]}"


def create_user(db: Session, payload: RegisterRequest, role: UserRole = UserRole.USER) -> User:
    """Create a new user. Raises ConflictError if email/username already taken."""
    if get_by_email(db, payload.email):
        raise ConflictError("Email is already registered")
    if get_by_username(db, payload.username):
        raise ConflictError("Username is already taken")
    user = User(
        email=payload.email,
        username=payload.username,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role=role,
        is_active=True,
        is_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_firebase_user(
    db: Session,
    firebase_uid: str,
    email: str | None,
    full_name: str | None = None,
    avatar_url: str | None = None,
    email_verified: bool = False,
    role: UserRole = UserRole.USER,
) -> User:
    """Create a user row from a Firebase identity (no password set)."""
    base_username = _derive_username(email, firebase_uid)
    username = base_username
    suffix = 0
    while get_by_username(db, username):
        suffix += 1
        username = f"{base_username}_{suffix}"[:100]

    if email and get_by_email(db, email):
        # Race-condition guard — another row already claimed this email.
        raise ConflictError("Email already registered through another provider")

    user = User(
        email=email or f"{firebase_uid}@firebase.local",
        username=username,
        password_hash="",  # Empty — Firebase handles auth.
        full_name=full_name,
        role=role,
        is_active=True,
        is_verified=email_verified,
        avatar_url=avatar_url,
        firebase_uid=firebase_uid,
        auth_provider="google",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, payload: LoginRequest) -> User:
    """Verify credentials and return the user. Raises UnauthorizedError otherwise."""
    user = get_by_email(db, payload.email)
    if user is None or not user.password_hash or not verify_password(payload.password, user.password_hash):
        raise UnauthorizedError("Invalid email or password")
    if not user.is_active:
        raise UnauthorizedError("User account is disabled")
    return user


def require_admin(user: User) -> None:
    if user.role != UserRole.ADMIN:
        raise BadRequestError("Admin privileges required")