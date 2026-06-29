"""User service: create, authenticate, fetch."""

from __future__ import annotations

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


def authenticate(db: Session, payload: LoginRequest) -> User:
    """Verify credentials and return the user. Raises UnauthorizedError otherwise."""
    user = get_by_email(db, payload.email)
    if user is None or not verify_password(payload.password, user.password_hash):
        raise UnauthorizedError("Invalid email or password")
    if not user.is_active:
        raise UnauthorizedError("User account is disabled")
    return user


def require_admin(user: User) -> None:
    if user.role != UserRole.ADMIN:
        raise BadRequestError("Admin privileges required")