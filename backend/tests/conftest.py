"""Shared pytest fixtures for the MailGuard-AI backend.

Why this file exists:
    Every test file used to repeat the same boilerplate (create sqlite db,
    override get_db, build a TestClient). Centralising it here means tests
    focus on behaviour, not setup.

Usage:
    def test_foo(client, db_session, regular_user_token):
        resp = client.get(...)
        assert resp.status_code == 200
"""

from __future__ import annotations

import os

# Ensure env vars are present before app modules import `settings`.
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("JWT_SECRET_KEY", "test_secret_for_pytest_only_xxxxxxxxxxxxxxxxxxxx")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_mailguard.db")
os.environ.setdefault("AI_PROVIDER", "stub")
os.environ.setdefault("FIREBASE_ENABLED", "false")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token, hash_password
from app.database.connection import Base, get_db
from app.main import app
from app.models.user import User
from app.core.constants import UserRole


@pytest.fixture(scope="session")
def engine():
    """One sqlite db per test session, in memory with StaticPool so the
    same connection is reused across threads (TestClient runs handlers
    in a threadpool)."""
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def db_session(engine):
    """Per-test transaction that rolls back, giving isolation."""
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection, autoflush=False, autocommit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def client(db_session):
    """FastAPI TestClient with `get_db` overridden to use the test session."""
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def regular_user(db_session) -> User:
    user = User(
        email="user@test.dev",
        username="user",
        password_hash=hash_password("Password123!"),
        full_name="Test User",
        role=UserRole.USER,
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def admin_user(db_session) -> User:
    admin = User(
        email="admin@test.dev",
        username="admin",
        password_hash=hash_password("AdminPass123!"),
        full_name="Test Admin",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


@pytest.fixture()
def auth_headers(regular_user) -> dict[str, str]:
    token = create_access_token(
        subject=regular_user.id,
        extra_claims={"email": regular_user.email, "role": regular_user.role.value},
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def admin_headers(admin_user) -> dict[str, str]:
    token = create_access_token(
        subject=admin_user.id,
        extra_claims={"email": admin_user.email, "role": admin_user.role.value},
    )
    return {"Authorization": f"Bearer {token}"}
