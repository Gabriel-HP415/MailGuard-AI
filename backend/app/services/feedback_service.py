"""Feedback service: human-in-the-loop corrections."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.errors import NotFoundError
from app.models.feedback import Feedback
from app.models.prediction import Prediction
from app.models.user import User
from app.schemas.feedback import FeedbackCreate


def create_feedback(db: Session, user: User, payload: FeedbackCreate) -> Feedback:
    pred = db.get(Prediction, payload.prediction_id)
    if pred is None or pred.user_id != user.id:
        raise NotFoundError("Prediction not found")
    fb = Feedback(
        prediction_id=payload.prediction_id,
        user_id=user.id,
        is_correct=payload.is_correct,
        correct_class=payload.correct_class,
        comment=payload.comment,
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)
    return fb


def list_feedback_for_user(db: Session, user: User, limit: int = 50, offset: int = 0) -> list[Feedback]:
    stmt = (
        select(Feedback)
        .where(Feedback.user_id == user.id)
        .order_by(Feedback.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(stmt))