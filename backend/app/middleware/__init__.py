"""Middleware: rate limit, request logging, CORS tweaks."""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from threading import Lock
from typing import Iterable

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.errors import AppError

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory IP-based rate limiter."""

    def __init__(self, app, requests_per_minute: int = 120, exempt_paths: Iterable[str] | None = None):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.exempt_paths = set(exempt_paths or ["/health", "/docs", "/redoc", "/openapi.json"])
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in self.exempt_paths:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window_start = now - 60.0

        with self._lock:
            hits = [t for t in self._hits[client_ip] if t >= window_start]
            if len(hits) >= self.requests_per_minute:
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"error": {"code": "rate_limited", "message": "Too many requests"}},
                )
            hits.append(now)
            self._hits[client_ip] = hits

        return await call_next(request)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs each request method/path/duration/status."""

    async def dispatch(self, request: Request, call_next):
        t0 = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        logger.info(
            "%s %s -> %s (%.1f ms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response