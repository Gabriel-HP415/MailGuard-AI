"""Email service: persist captured email content."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.errors import NotFoundError
from app.models.email import Email
from app.models.user import User
from app.schemas.email import EmailCreate


def create_email(db: Session, user: User, payload: EmailCreate) -> Email:
    email = Email(
        user_id=user.id,
        gmail_id=payload.gmail_id,
        sender=payload.sender,
        sender_domain=payload.sender_domain,
        recipient=payload.recipient,
        subject=payload.subject,
        body_text=payload.body_text,
        body_html=payload.body_html,
        links=payload.links,
        attachments=payload.attachments,
        has_attachments=bool(payload.attachments),
        received_at=payload.received_at,
    )
    db.add(email)
    db.commit()
    db.refresh(email)
    return email


def list_user_emails(db: Session, user: User, limit: int = 50, offset: int = 0) -> list[Email]:
    stmt = (
        select(Email)
        .where(Email.user_id == user.id)
        .order_by(Email.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(stmt))


def get_email(db: Session, user: User, email_id: int) -> Email:
    email = db.get(Email, email_id)
    if email is None or email.user_id != user.id:
        raise NotFoundError(f"Email {email_id} not found")
    return email