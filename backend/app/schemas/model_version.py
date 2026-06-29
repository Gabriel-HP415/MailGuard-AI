"""Model version Pydantic schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ModelVersionCreate(BaseModel):
    """Payload for registering a new model version (admin only)."""

    version: str
    algorithm: str
    description: Optional[str] = None
    accuracy: Optional[float] = None
    precision_score: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None
    training_samples: Optional[int] = None
    training_duration_sec: Optional[int] = None
    file_path: Optional[str] = None
    metrics: Optional[dict] = None


class ModelVersionUpdate(BaseModel):
    """Payload for updating a model version (activate/deactivate)."""

    is_active: Optional[bool] = None
    description: Optional[str] = None


class ModelVersionRead(BaseModel):
    """Model version record."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    version: str
    algorithm: str
    description: Optional[str] = None
    accuracy: Optional[float] = None
    precision_score: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None
    training_samples: Optional[int] = None
    training_duration_sec: Optional[int] = None
    file_path: Optional[str] = None
    metrics: Optional[dict] = None
    is_active: bool
    created_at: datetime