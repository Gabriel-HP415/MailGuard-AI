"""Tests for the auth endpoints."""

from __future__ import annotations

import os

os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_NAME", "mailguard_ai")
os.environ.setdefault("DB_USER", "mailguard")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("JWT_SECRET_KEY", "test_secret_test_secret_test_secret_xxxx")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.database.connection import Base, get_db
from app.main import app
from app.models.user import User
from app.core.constants import UserRole


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = Session()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_register_and_login(client, db_session):
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": "user@example.com",
            "username": "user",
            "password": "Password123",
            "full_name": "Test User",
        },
    )
    assert resp.status_code == 201, resp.text
    user = resp.json()
    assert user["email"] == "user@example.com"

    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "Password123"},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    assert token

    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "user@example.com"


def test_login_invalid_password(client, db_session):
    db_session.add(
        User(
            email="u@e.com",
            username="u",
            password_hash=hash_password("CorrectPassword1!"),
            role=UserRole.USER,
            is_active=True,
        )
    )
    db_session.commit()
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "u@e.com", "password": "WrongPassword"},
    )
    assert resp.status_code == 401