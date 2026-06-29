"""FastAPI application factory for MailGuard-AI."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.errors import register_exception_handlers
from app.api.v1 import api_router
from app.core.config import settings
from app.middleware import RateLimitMiddleware, RequestLoggingMiddleware
from app.services import firebase_auth as firebase_auth_service

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(_: FastAPI):
    logger.info("MailGuard-AI backend starting (env=%s)", settings.app_env)
    if settings.firebase_enabled:
        firebase_auth_service.init_firebase(
            credentials_path=settings.firebase_credentials_path,
            project_id=settings.firebase_project_id,
            credentials_json=getattr(settings, "firebase_credentials_json", None) or None,
        )
    else:
        logger.info("Firebase authentication disabled (FIREBASE_ENABLED=false)")
    yield
    logger.info("MailGuard-AI backend shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="MailGuard-AI — phishing & scam email detection API.",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=_lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate limiting
    app.add_middleware(
        RateLimitMiddleware,
        requests_per_minute=settings.rate_limit_per_minute,
    )

    # Request logging
    app.add_middleware(RequestLoggingMiddleware)

    # Exception handlers
    register_exception_handlers(app)

    # Routers
    app.include_router(api_router, prefix="/api/v1")

    @app.get("/health", tags=["System"])
    async def health():
        return {
            "status": "ok",
            "service": settings.app_name,
            "version": settings.app_version,
            "env": settings.app_env,
        }

    @app.get("/api/v1/health", tags=["System"], include_in_schema=False)
    async def health_v1():
        # Mirror of /health at the v1 prefix used by Render's health check.
        return await health()

    @app.get("/", tags=["System"], include_in_schema=False)
    async def root():
        return JSONResponse(
            {
                "service": settings.app_name,
                "version": settings.app_version,
                "docs": "/docs",
                "api": "/api/v1",
            }
        )

    return app


app = create_app()