"""Pydantic schemas exposed by the AI Service."""

from typing import Optional

from pydantic import BaseModel, Field

from ai_service.app.constants import EmailClass


class EmailInput(BaseModel):
    """Input payload for a single email to classify."""

    subject: Optional[str] = ""
    body: str = Field(min_length=1, description="Plain-text body (or HTML-stripped text).")
    sender: Optional[str] = None
    sender_domain: Optional[str] = None
    links: Optional[list[str]] = None
    attachments: Optional[list[dict]] = None


class PredictionOutput(BaseModel):
    """Result of a single prediction."""

    predicted_class: EmailClass
    class_index: int
    confidence: float
    probabilities: dict[str, float]
    risk_score: float
    threat_level: str
    inference_time_ms: int
    model_version: str
    model_algorithm: str
    explanation: dict
    highlighted_spans: list[dict] = []
    suspicious_urls: list[dict] = []


class BatchPredictionRequest(BaseModel):
    """Batch of emails."""

    emails: list[EmailInput]
    include_explanation: bool = True


class BatchPredictionResponse(BaseModel):
    """Batch prediction result."""

    results: list[PredictionOutput]
    total: int
    model_version: str


class HealthResponse(BaseModel):
    """Service health status."""

    status: str
    model_loaded: bool
    active_version: Optional[str] = None
    device: str
    uptime_seconds: float
    ab_test_enabled: bool = False