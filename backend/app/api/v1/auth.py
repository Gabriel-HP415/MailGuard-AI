"""Authentication endpoints: register, login, me."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.security import create_access_token
from app.database.connection import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.services import activity_log_service, user_service

router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    """Register a new user and return a backend JWT — no separate /login needed."""
    user = user_service.create_user(db, payload)
    activity_log_service.log(
        db, user=user, action="register",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    token = create_access_token(
        subject=user.id,
        extra_claims={"email": user.email, "role": user.role.value},
    )
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = user_service.authenticate(db, payload)
    user.last_login_at = __import__("datetime").datetime.utcnow()
    db.commit()
    db.refresh(user)

    token = create_access_token(
        subject=user.id,
        extra_claims={"email": user.email, "role": user.role.value},
    )
    activity_log_service.log(
        db, user=user, action="login",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user