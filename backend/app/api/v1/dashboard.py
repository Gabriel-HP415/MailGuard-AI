"""Dashboard endpoints — aggregated statistics for the current user."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.connection import get_db
from app.models.user import User
from app.services import prediction_service
from app.services.ai_client import ai_client

router = APIRouter()


@router.get("/stats")
async def get_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    days: int = Query(30, ge=1, le=365),
) -> dict[str, Any]:
    """Aggregate stats for the user's predictions over the last N days."""
    return prediction_service.stats_for_user(db, current_user, days=days)


@router.get("/recent")
async def recent_predictions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(10, ge=1, le=50),
) -> dict[str, Any]:
    """Return the most recent predictions for the dashboard."""
    preds = prediction_service.list_user_predictions(db, current_user, limit=limit)
    items = []
    for p in preds:
        items.append({
            "id": p.id,
            "email_id": p.email_id,
            "predicted_class": p.predicted_class.value
                if hasattr(p.predicted_class, "value") else str(p.predicted_class),
            "class_index": p.class_index,
            "confidence": float(p.confidence),
            "risk_score": float(p.risk_score),
            "threat_level": p.threat_level.value
                if hasattr(p.threat_level, "value") else str(p.threat_level),
            "probabilities": p.probabilities,
            "explanation": p.explanation,
            "suspicious_urls": p.suspicious_urls,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        })
    return {"results": items, "total": len(items)}


@router.get("/ai/health")
async def ai_service_health() -> dict[str, Any]:
    """Check the AI service health (for the dashboard)."""
    return await ai_client.health()