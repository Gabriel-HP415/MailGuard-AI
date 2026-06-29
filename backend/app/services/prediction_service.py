"""Prediction service: persist AI predictions and fetch history."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.errors import BadRequestError, NotFoundError
from app.core.constants import INDEX_TO_CLASS, ThreatLevel
from app.models.email import Email
from app.models.model_version import ModelVersion
from app.models.prediction import Prediction
from app.models.user import User
from app.schemas.prediction import PredictionRequest


def _resolve_model_version(db: Session, requested: str | None) -> ModelVersion:
    """Look up a model version by name, or fall back to the active one."""
    if requested and requested not in {"auto", ""}:
        mv = db.scalar(
            select(ModelVersion).where(ModelVersion.version == requested)
        )
        if mv is None:
            raise NotFoundError(f"Model version '{requested}' not found")
        return mv
    mv = db.scalar(select(ModelVersion).where(ModelVersion.is_active.is_(True)))
    if mv is None:
        raise BadRequestError("No active model version configured")
    return mv


def save_prediction(
    db: Session,
    user: User,
    email: Email,
    model_version: ModelVersion,
    ai_result: dict[str, Any],
) -> Prediction:
    """Persist a prediction record from the AI Service output."""
    probabilities = ai_result.get("probabilities") or {}
    probs_list = [
        float(probabilities.get(INDEX_TO_CLASS.get(i, ""), 0.0))
        for i in range(len(INDEX_TO_CLASS))
    ]

    pred = Prediction(
        email_id=email.id,
        user_id=user.id,
        model_version_id=model_version.id,
        predicted_class=ai_result["predicted_class"],
        class_index=int(ai_result["class_index"]),
        confidence=float(ai_result["confidence"]),
        risk_score=float(ai_result["risk_score"]),
        threat_level=ThreatLevel(ai_result.get("threat_level", "low")),
        probabilities=probs_list,
        explanation=ai_result.get("explanation"),
        highlighted_spans=ai_result.get("highlighted_spans"),
        suspicious_urls=ai_result.get("suspicious_urls"),
        inference_time_ms=ai_result.get("inference_time_ms"),
    )
    db.add(pred)
    db.commit()
    db.refresh(pred)
    return pred


def get_prediction(db: Session, user: User, prediction_id: int) -> Prediction:
    pred = db.get(Prediction, prediction_id)
    if pred is None or pred.user_id != user.id:
        raise NotFoundError(f"Prediction {prediction_id} not found")
    return pred


def list_user_predictions(
    db: Session,
    user: User,
    *,
    predicted_class: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Prediction]:
    stmt = select(Prediction).where(Prediction.user_id == user.id)
    if predicted_class:
        stmt = stmt.where(Prediction.predicted_class == predicted_class)
    stmt = stmt.order_by(Prediction.created_at.desc()).limit(limit).offset(offset)
    return list(db.scalars(stmt))


def stats_for_user(db: Session, user: User, days: int = 30) -> dict[str, Any]:
    """Aggregate stats for the user dashboard."""
    since = datetime.utcnow() - timedelta(days=days)
    total = db.scalar(
        select(func.count(Prediction.id)).where(
            Prediction.user_id == user.id, Prediction.created_at >= since
        )
    ) or 0

    by_class: dict[str, int] = {}
    for row in db.execute(
        select(Prediction.predicted_class, func.count(Prediction.id))
        .where(Prediction.user_id == user.id, Prediction.created_at >= since)
        .group_by(Prediction.predicted_class)
    ):
        by_class[row[0].value if hasattr(row[0], "value") else str(row[0])] = int(row[1])

    by_threat: dict[str, int] = {}
    for row in db.execute(
        select(Prediction.threat_level, func.count(Prediction.id))
        .where(Prediction.user_id == user.id, Prediction.created_at >= since)
        .group_by(Prediction.threat_level)
    ):
        by_threat[row[0].value if hasattr(row[0], "value") else str(row[0])] = int(row[1])

    avg_risk = db.scalar(
        select(func.avg(Prediction.risk_score)).where(
            Prediction.user_id == user.id, Prediction.created_at >= since
        )
    )
    return {
        "total": int(total),
        "by_class": by_class,
        "by_threat": by_threat,
        "avg_risk": float(avg_risk or 0.0),
        "days": days,
    }