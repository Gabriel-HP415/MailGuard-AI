"""Admin endpoints — model version management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.database.connection import get_db
from app.models.model_version import ModelVersion
from app.models.user import User
from app.schemas.model_version import ModelVersionCreate, ModelVersionRead, ModelVersionUpdate

router = APIRouter()


@router.get("/models", response_model=list[ModelVersionRead])
def list_models(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    stmt = (
        select(ModelVersion)
        .order_by(ModelVersion.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(stmt))


@router.post("/models", response_model=ModelVersionRead, status_code=201)
def create_model(
    payload: ModelVersionCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    mv = ModelVersion(**payload.model_dump())
    db.add(mv)
    db.commit()
    db.refresh(mv)
    return mv


@router.patch("/models/{model_id}", response_model=ModelVersionRead)
def update_model(
    model_id: int,
    payload: ModelVersionUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    mv = db.get(ModelVersion, model_id)
    if mv is None:
        from app.api.errors import NotFoundError
        raise NotFoundError("Model version not found")
    if payload.is_active is True:
        # Deactivate all others
        for other in db.scalars(select(ModelVersion)).all():
            other.is_active = False
        mv.is_active = True
    elif payload.is_active is False:
        mv.is_active = False
    if payload.description is not None:
        mv.description = payload.description
    db.commit()
    db.refresh(mv)
    return mv


@router.post("/models/{model_id}/activate", response_model=ModelVersionRead)
def activate_model(
    model_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    mv = db.get(ModelVersion, model_id)
    if mv is None:
        from app.api.errors import NotFoundError
        raise NotFoundError("Model version not found")
    for other in db.scalars(select(ModelVersion)).all():
        other.is_active = False
    mv.is_active = True
    db.commit()
    db.refresh(mv)
    return mv