"""Feedback endpoints (Human-in-the-loop)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.connection import get_db
from app.models.user import User
from app.schemas.feedback import FeedbackCreate, FeedbackRead
from app.services import activity_log_service, feedback_service

router = APIRouter()


@router.post("", response_model=FeedbackRead, status_code=201)
def create_feedback(
    payload: FeedbackCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    fb = feedback_service.create_feedback(db, current_user, payload)
    activity_log_service.log(
        db, user=current_user, action="feedback",
        entity_type="prediction", entity_id=payload.prediction_id,
        details={"is_correct": payload.is_correct, "correct_class": payload.correct_class.value if payload.correct_class else None},
    )
    return fb


@router.get("", response_model=list[FeedbackRead])
def list_feedback(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return feedback_service.list_feedback_for_user(db, current_user, limit=limit, offset=offset)