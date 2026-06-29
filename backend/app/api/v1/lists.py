"""Whitelist & Blacklist endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.connection import get_db
from app.models.user import User
from app.schemas.lists import BlacklistRead, BlacklistWrite, WhitelistRead, WhitelistWrite
from app.services import list_service

router = APIRouter()


# ---------- Whitelist ----------
@router.post("/whitelist", response_model=WhitelistRead, status_code=201)
def add_whitelist(
    payload: WhitelistWrite,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_service.add_to_whitelist(db, current_user, payload)


@router.get("/whitelist", response_model=list[WhitelistRead])
def list_whitelist(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_service.list_whitelist(db, current_user)


@router.delete("/whitelist/{item_id}", status_code=204)
def delete_whitelist(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    list_service.remove_whitelist(db, current_user, item_id)
    return None


# ---------- Blacklist ----------
@router.post("/blacklist", response_model=BlacklistRead, status_code=201)
def add_blacklist(
    payload: BlacklistWrite,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_service.add_to_blacklist(db, current_user, payload)


@router.get("/blacklist", response_model=list[BlacklistRead])
def list_blacklist(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_service.list_blacklist(db, current_user)


@router.delete("/blacklist/{item_id}", status_code=204)
def delete_blacklist(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    list_service.remove_blacklist(db, current_user, item_id)
    return None