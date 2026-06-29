"""Prediction endpoints: classify an email by calling the AI Service."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.connection import get_db
from app.models.user import User
from app.schemas.prediction import PredictionRead, PredictionRequest
from app.services import (
    activity_log_service,
    email_service,
    prediction_service,
)
from app.services.ai_client import ai_client

router = APIRouter()


@router.post("", response_model=PredictionRead, status_code=201)
async def predict(
    payload: PredictionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Classify an email via the AI Service and persist the result."""
    # 1. Persist the email
    email = email_service.create_email(db, current_user, payload.email)

    # 2. Call the AI service
    ai_result = await ai_client.predict(payload)

    # 3. Resolve the model version
    model_version = prediction_service._resolve_model_version(db, payload.model_version)

    # 4. Save prediction
    prediction = prediction_service.save_prediction(
        db, current_user, email, model_version, ai_result
    )

    activity_log_service.log(
        db, user=current_user, action="predict",
        entity_type="email", entity_id=email.id,
        details={"prediction_id": prediction.id, "predicted_class": prediction.predicted_class.value},
    )
    return prediction


@router.get("", response_model=list[PredictionRead])
def list_predictions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    predicted_class: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return prediction_service.list_user_predictions(
        db, current_user, predicted_class=predicted_class, limit=limit, offset=offset
    )


@router.get("/{prediction_id}", response_model=PredictionRead)
def get_prediction(
    prediction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return prediction_service.get_prediction(db, current_user, prediction_id)