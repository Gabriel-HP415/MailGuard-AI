"""Prediction-related Pydantic schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import EmailClass, ThreatLevel
from app.schemas.email import EmailCreate


class PredictionRequest(BaseModel):
    """Request payload for predicting the class of an email."""

    email: EmailCreate
    model_version: Optional[str] = Field(
        default=None,
        description="Specific model version. Use null/auto for the active model.",
    )
    include_explanation: bool = True


class PredictionRead(BaseModel):
    """Full prediction record."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email_id: int
    user_id: int
    model_version_id: int
    predicted_class: EmailClass
    class_index: int
    confidence: float
    risk_score: float
    threat_level: ThreatLevel
    probabilities: Optional[list[float]] = None
    explanation: Optional[dict] = None
    highlighted_spans: Optional[list[dict]] = None
    suspicious_urls: Optional[list[dict]] = None
    inference_time_ms: Optional[int] = None
    created_at: datetime