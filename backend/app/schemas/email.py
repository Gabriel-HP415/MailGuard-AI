"""Email-related Pydantic schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class EmailCreate(BaseModel):
    """Payload sent from the Chrome extension to register an email for analysis."""

    gmail_id: Optional[str] = Field(default=None, max_length=255)
    sender: str = Field(min_length=1, max_length=255)
    sender_domain: Optional[str] = Field(default=None, max_length=255)
    recipient: Optional[str] = Field(default=None, max_length=255)
    subject: Optional[str] = Field(default=None, max_length=1000)
    body_text: Optional[str] = None
    body_html: Optional[str] = None
    links: Optional[list[str]] = None
    attachments: Optional[list[dict]] = None
    received_at: Optional[datetime] = None


class EmailRead(BaseModel):
    """Email record as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    gmail_id: Optional[str] = None
    sender: str
    sender_domain: Optional[str] = None
    recipient: Optional[str] = None
    subject: Optional[str] = None
    body_text: Optional[str] = None
    has_attachments: bool
    received_at: Optional[datetime] = None
    created_at: datetime