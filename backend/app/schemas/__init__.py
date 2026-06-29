"""Pydantic schemas package for MailGuard-AI."""

from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.schemas.email import EmailCreate, EmailRead
from app.schemas.feedback import FeedbackCreate, FeedbackRead
from app.schemas.lists import BlacklistRead, BlacklistWrite, WhitelistRead, WhitelistWrite
from app.schemas.model_version import ModelVersionCreate, ModelVersionRead, ModelVersionUpdate
from app.schemas.prediction import PredictionRead, PredictionRequest

__all__ = [
    "BlacklistRead",
    "BlacklistWrite",
    "EmailCreate",
    "EmailRead",
    "FeedbackCreate",
    "FeedbackRead",
    "LoginRequest",
    "ModelVersionCreate",
    "ModelVersionRead",
    "ModelVersionUpdate",
    "PredictionRead",
    "PredictionRequest",
    "RegisterRequest",
    "TokenResponse",
    "UserResponse",
    "WhitelistRead",
    "WhitelistWrite",
]
