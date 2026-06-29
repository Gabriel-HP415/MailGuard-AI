"""Service layer (CRUD / business logic) for MailGuard-AI backend."""

from app.services import activity_log_service, email_service, feedback_service, prediction_service, user_service

__all__ = [
    "activity_log_service",
    "email_service",
    "feedback_service",
    "prediction_service",
    "user_service",
]