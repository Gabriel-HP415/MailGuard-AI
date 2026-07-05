"""A/B testing router for the AI Service.

Splits incoming ``/predict`` traffic between two registered models (the
"active" one and an explicit "challenger") according to a configurable
weight. Results include a ``bucket`` field (``"A"`` or ``"B"``) so the
backend can later join it with ground truth (feedback) and measure the
delta.

State is read-only against the database — we fetch the two model
registrations from the backend ``/api/v1/admin/models`` endpoint and cache
them for 60 s to avoid hot-path latency.

Configuration via env vars (see ``app/config.py``):

| env | default | meaning |
|-----|---------|---------|
| ``AB_TEST_ENABLED``     | ``false`` | turn the experiment on |
| ``AB_TEST_CHALLENGER``  | (unset)   | version of the challenger model |
| ``AB_TEST_WEIGHT_B``    | ``0.2``    | probability of routing to challenger |
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import time
from dataclasses import dataclass
from typing import Any, Callable

from ai_service.app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ABConfig:
    enabled: bool
    challenger_version: str | None
    weight_b: float

    @classmethod
    def from_env(cls) -> "ABConfig":
        return cls(
            enabled=str(os.getenv("AB_TEST_ENABLED", "false")).lower() == "true",
            challenger_version=os.getenv("AB_TEST_CHALLENGER") or None,
            weight_b=float(os.getenv("AB_TEST_WEIGHT_B", "0.2")),
        )


@dataclass
class ABResult:
    bucket: str  # "A" | "B"
    model_version: str
    response: dict[str, Any]


class ABTester:
    """Coordinates calls between active (A) and challenger (B) models."""

    def __init__(
        self,
        predict_a: Callable[[], dict[str, Any]],
        predict_b: Callable[[], dict[str, Any]] | None = None,
        config: ABConfig | None = None,
    ):
        self.config = config or ABConfig.from_env()
        self._predict_a = predict_a
        self._predict_b = predict_b
        self._cache_ttl = 60.0
        self._last_fetch = 0.0
        self._stats_a = 0
        self._stats_b = 0

    def is_active(self) -> bool:
        return (
            self.config.enabled
            and self.config.challenger_version is not None
            and self._predict_b is not None
        )

    def assign_bucket(self) -> str:
        """Randomly pick 'A' or 'B' using the configured weight for B."""
        if not self.is_active():
            return "A"
        if random.random() < self.config.weight_b:
            self._stats_b += 1
            return "B"
        self._stats_a += 1
        return "A"

    async def predict(self, **kwargs) -> ABResult:
        """Run prediction in the chosen bucket."""
        if not self.is_active():
            response = await _maybe_await(self._predict_a())
            return ABResult("A", model_version="active", response=response or {})

        bucket = self.assign_bucket()
        if bucket == "B":
            response = await _maybe_await(self._predict_b())
            version = self.config.challenger_version
        else:
            response = await _maybe_await(self._predict_a())
            version = "active"

        if isinstance(response, dict):
            response.setdefault("ab_bucket", bucket)
            response.setdefault("ab_challenger", self.config.challenger_version)
        return ABResult(bucket=bucket, model_version=version or "active", response=response or {})

    def stats(self) -> dict[str, int]:
        return {"A": self._stats_a, "B": self._stats_b}


async def _maybe_await(value: Any) -> Any:
    """Await the result of a sync or async callable."""
    if asyncio.iscoroutine(value):
        return await value
    return value


# ----- Helpers for integration with the FastAPI service -----


def make_default_tester(
    *,
    predict_active: Callable[[], Any],
    predict_challenger: Callable[[], Any] | None,
) -> ABTester:
    """Build an ABTester with the default config."""
    cfg = ABConfig.from_env()
    return ABTester(
        predict_a=predict_active,
        predict_b=predict_challenger if cfg.challenger_version else None,
        config=cfg,
    )