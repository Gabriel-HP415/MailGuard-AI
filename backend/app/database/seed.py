"""Database seed script — populates initial data.

Run with:
    python -m app.database.seed
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import ModelAlgorithm, UserRole
from app.core.security import hash_password
from app.database.connection import SessionLocal
from app.models.feedback import Feedback
from app.models.model_version import ModelVersion
from app.models.user import User

logger = logging.getLogger(__name__)


def seed_admin(db: Session) -> Optional[User]:
    """Create a default admin user if no admin exists yet."""
    admin = db.query(User).filter(User.role == UserRole.ADMIN).first()
    if admin:
        logger.info("Admin user already exists: %s", admin.email)
        return admin

    admin = User(
        email=settings.admin_email,
        username="admin",
        password_hash=hash_password(settings.admin_password),
        full_name="System Administrator",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    logger.info("Created admin user: %s", admin.email)
    return admin


def seed_demo_user(db: Session) -> Optional[User]:
    """Create a demo end-user so devs have something to log in with.

    Only created in dev mode (settings.app_env == 'development')."""
    if settings.app_env != "development":
        return None

    demo_email = "demo@localhost.dev"
    if db.query(User).filter(User.email == demo_email).first():
        return None

    demo = User(
        email=demo_email,
        username="demo",
        password_hash=hash_password("Demo1234!"),
        full_name="Demo User",
        role=UserRole.USER,
        is_active=True,
        is_verified=True,
        auth_provider="email",
    )
    db.add(demo)
    db.commit()
    db.refresh(demo)
    logger.info("Created demo user: %s / password=Demo1234!", demo_email)
    return demo


def seed_default_model(db: Session) -> Optional[ModelVersion]:
    """Register a default (placeholder) model version."""
    default_version = "v1.0.0-baseline"
    existing = (
        db.query(ModelVersion)
        .filter(ModelVersion.version == default_version)
        .first()
    )
    if existing:
        logger.info("Default model version already exists: %s", default_version)
        return existing

    model = ModelVersion(
        version=default_version,
        algorithm=ModelAlgorithm.DISTILBERT.value,
        description="Initial placeholder model version. Train the real pipeline to publish new versions.",
        accuracy=None,
        is_active=True,
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    logger.info("Created default model version: %s", model.version)
    return model


def run_seed() -> None:
    """Run all seeders in a single transaction-ish flow."""
    db = SessionLocal()
    try:
        seed_admin(db)
        seed_demo_user(db)
        seed_default_model(db)
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_seed()