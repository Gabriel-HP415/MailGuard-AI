"""Whitelist & Blacklist services."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.errors import ConflictError, NotFoundError
from app.models.blacklist import Blacklist
from app.models.user import User
from app.models.whitelist import Whitelist
from app.schemas.lists import BlacklistWrite, WhitelistWrite


# ---------- Whitelist ----------

def add_to_whitelist(db: Session, user: User, payload: WhitelistWrite) -> Whitelist:
    existing = db.scalar(
        select(Whitelist).where(
            Whitelist.user_id == user.id, Whitelist.sender == payload.sender
        )
    )
    if existing:
        raise ConflictError("Sender already in whitelist")
    item = Whitelist(
        user_id=user.id,
        sender=payload.sender,
        domain=payload.domain,
        note=payload.note,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def list_whitelist(db: Session, user: User) -> list[Whitelist]:
    stmt = select(Whitelist).where(Whitelist.user_id == user.id).order_by(Whitelist.created_at.desc())
    return list(db.scalars(stmt))


def remove_whitelist(db: Session, user: User, item_id: int) -> None:
    item = db.get(Whitelist, item_id)
    if item is None or item.user_id != user.id:
        raise NotFoundError("Whitelist entry not found")
    db.delete(item)
    db.commit()


# ---------- Blacklist ----------

def add_to_blacklist(db: Session, user: User, payload: BlacklistWrite) -> Blacklist:
    existing = db.scalar(
        select(Blacklist).where(
            Blacklist.user_id == user.id, Blacklist.sender == payload.sender
        )
    )
    if existing:
        raise ConflictError("Sender already in blacklist")
    item = Blacklist(
        user_id=user.id,
        sender=payload.sender,
        domain=payload.domain,
        reason=payload.reason,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def list_blacklist(db: Session, user: User) -> list[Blacklist]:
    stmt = select(Blacklist).where(Blacklist.user_id == user.id).order_by(Blacklist.created_at.desc())
    return list(db.scalars(stmt))


def remove_blacklist(db: Session, user: User, item_id: int) -> None:
    item = db.get(Blacklist, item_id)
    if item is None or item.user_id != user.id:
        raise NotFoundError("Blacklist entry not found")
    db.delete(item)
    db.commit()