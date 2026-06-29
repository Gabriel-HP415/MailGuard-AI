"""Whitelist & Blacklist Pydantic schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class WhitelistWrite(BaseModel):
    """Payload to add an entry to the whitelist."""

    sender: str = Field(min_length=1, max_length=255)
    domain: Optional[str] = Field(default=None, max_length=255)
    note: Optional[str] = Field(default=None, max_length=500)


class WhitelistRead(BaseModel):
    """Whitelist entry as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    sender: str
    domain: Optional[str] = None
    note: Optional[str] = None
    created_at: datetime


class BlacklistWrite(BaseModel):
    """Payload to add an entry to the blacklist."""

    sender: str = Field(min_length=1, max_length=255)
    domain: Optional[str] = Field(default=None, max_length=255)
    reason: Optional[str] = Field(default=None, max_length=500)


class BlacklistRead(BaseModel):
    """Blacklist entry as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    sender: str
    domain: Optional[str] = None
    reason: Optional[str] = None
    created_at: datetime