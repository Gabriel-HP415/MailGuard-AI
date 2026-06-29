"""Feedback-related Pydantic schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.core.constants import EmailClass


class FeedbackCreate(BaseModel):
    """Payload for submitting user feedback on a prediction."""

    prediction_id: int
    is_correct: bool
    correct_class: Optional[EmailClass] = None
    comment: Optional[str] = None


class FeedbackRead(BaseModel):
    """Feedback record."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    prediction_id: int
    user_id: int
    is_correct: bool
    correct_class: Optional[EmailClass] = None
    comment: Optional[str] = None
    created_at: datetime