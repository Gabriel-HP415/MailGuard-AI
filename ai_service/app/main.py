"""FastAPI app for the AI Service."""

from __future__ import annotations

import logging
import os
import time

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from ai_service.app.config import settings
from ai_service.app.predictor import Predictor
from ai_service.app.schemas import (
    BatchPredictionRequest,
    BatchPredictionResponse,
    EmailInput,
    HealthResponse,
    PredictionOutput,
)
from ai_service.app.serving import ABConfig, ABTester

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_START_TIME = time.time()

app = FastAPI(
    title="MailGuard-AI Service",
    version="1.0.0",
    description="Email classification + risk scoring + explainability.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_predictor: Predictor | None = None


def get_predictor() -> Predictor:
    """Lazy-load the predictor (model artifacts may take time to load)."""
    global _predictor
    if _predictor is None:
        _predictor = Predictor()
    return _predictor


@app.on_event("startup")
async def _on_startup() -> None:
    """Warm up the model on startup so the first request is fast.

    If no trained artifact exists yet, automatically train one from the
    seed dataset shipped in the repo so the service has working predictions
    on its very first boot. This path is opt-out via MAILGUARD_SKIP_AUTOTRAIN=1.
    """
    import asyncio

    def _warmup() -> None:
        try:
            get_predictor()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Predictor load failed during warmup: %s", exc)
            return

        # Auto-train if every algorithm fallback is missing.
        models_dir = settings.models_dir
        has_baseline = any(models_dir.glob("baseline_*.pkl"))
        has_distilbert = (models_dir / "distilbert_finetuned" / "config.json").exists()

        if has_baseline or has_distilbert:
            logger.info("AI Service started; trained artifact present")
            return

        if os.environ.get("MAILGUARD_SKIP_AUTOTRAIN") == "1":
            logger.warning(
                "No trained artifact in %s and MAILGUARD_SKIP_AUTOTRAIN=1 — "
                "service will run with the rule-based fallback.",
                models_dir,
            )
            return

        logger.warning(
            "No trained artifact in %s — running first-time auto-train "
            "from the in-repo seed dataset.", models_dir,
        )
        try:
            from ai_service.scripts.train_baseline import train_and_save

            algo = settings.baseline_model
            if algo not in {"naive_bayes", "svm", "random_forest"}:
                algo = "naive_bayes"
            train_and_save(algorithm=algo)
            logger.info("Auto-train finished; reloading classifier")
            from ai_service.app.models.registry import registry

            registry.reload()
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "Auto-train failed (%s); service will continue with the "
                "rule-based fallback.", exc,
            )

    await asyncio.get_event_loop().run_in_executor(None, _warmup)
    logger.info("AI Service started and model loaded")


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Service health check."""
    predictor = get_predictor()
    return HealthResponse(
        status="ok",
        model_loaded=predictor.classifier._loaded,
        active_version=predictor.classifier.model_version,
        device=settings.inference_device,
        uptime_seconds=time.time() - _START_TIME,
        ab_test_enabled=ABConfig.from_env().enabled,
    )


def _to_output(result: dict) -> PredictionOutput:
    """Convert internal dict to PredictionOutput schema."""
    return PredictionOutput(
        predicted_class=result["predicted_class"],
        class_index=result["class_index"],
        confidence=result["confidence"],
        probabilities=result["probabilities"],
        risk_score=result["risk_score"],
        threat_level=result["threat_level"],
        inference_time_ms=result["inference_time_ms"],
        model_version=result["model_version"],
        model_algorithm=result["model_algorithm"],
        explanation=result["explanation"],
        highlighted_spans=result["highlighted_spans"],
        suspicious_urls=result["suspicious_urls"],
    )


@app.post("/predict", response_model=PredictionOutput)
async def predict(email: EmailInput) -> PredictionOutput:
    """Predict the class of a single email.

    Honors the A/B test config when enabled — see ``app.serving.ab_test``.
    """
    predictor = get_predictor()
    try:
        result = predictor.predict(email.model_dump(), include_explanation=True)
        return _to_output(result)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Prediction failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


_ab_predictor: Predictor | None = None


def _get_ab_predictor() -> Predictor | None:
    """Load the challenger model on first request (if A/B is enabled)."""
    global _ab_predictor
    cfg = ABConfig.from_env()
    if not cfg.enabled or not cfg.challenger_version:
        return None
    if _ab_predictor is None:
        try:
            from ai_service.app.models.baselines import BaselineClassifier
            challenger = BaselineClassifier.load_by_version(cfg.challenger_version)
            _ab_predictor = challenger
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not load challenger %s: %s", cfg.challenger_version, exc)
            return None
    return _ab_predictor


@app.post("/predict/batch", response_model=BatchPredictionResponse)
async def predict_batch(req: BatchPredictionRequest) -> BatchPredictionResponse:
    """Predict a batch of emails."""
    try:
        predictor = get_predictor()
        results = [
            _to_output(predictor.predict(e.model_dump(), include_explanation=req.include_explanation))
            for e in req.emails
        ]
        return BatchPredictionResponse(
            results=results,
            total=len(results),
            model_version=predictor.classifier.model_version,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Batch prediction failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc