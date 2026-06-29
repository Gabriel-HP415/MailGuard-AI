"""Email endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.connection import get_db
from app.models.user import User
from app.schemas.email import EmailCreate, EmailRead
from app.services import email_service

router = APIRouter()


@router.post("", response_model=EmailRead, status_code=201)
def create_email(
    payload: EmailCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit a captured email for storage (without AI prediction)."""
    return email_service.create_email(db, current_user, payload)


@router.get("", response_model=list[EmailRead])
def list_emails(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return email_service.list_user_emails(db, current_user, limit=limit, offset=offset)


@router.get("/{email_id}", response_model=EmailRead)
def get_email(
    email_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return email_service.get_email(db, current_user, email_id)