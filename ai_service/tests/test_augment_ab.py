"""Tests for the augmentation, AB testing, and evaluation script."""

from __future__ import annotations

from collections import Counter

from ai_service.app.preprocessing.augment import (
    augment_dataset,
    augment_text,
    class_distribution,
)
from ai_service.app.serving.ab_test import ABConfig, ABTester, make_default_tester


def test_augment_text_keeps_meaningful_variants():
    base = "Please verify your account immediately. Click here to continue."
    variants = augment_text(
        base,
        strategies=("synonym", "shuffle", "url_noise", "invisible"),
        rng=__import__("random").Random(0),
    )
    assert len(variants) == 4
    # Every variant should still contain at least one of the keywords
    for v in variants:
        low = v.lower()
        assert any(k in low for k in ["verify", "confirm", "validate"])


def test_augment_dataset_grows_minority_classes():
    samples = [
        ("normal", "Hi", "Let's grab coffee"),
        ("scam", "Verify", "Please verify your account"),
        ("scam", "Urgent", "Your account is suspended"),
        ("spam", "Offer", "Free offer click here"),
    ]
    out = augment_dataset(samples, target_classes=("scam", "spam"), multiplier=2, seed=1)
    counts = Counter(s for s, *_ in out)
    # 4 originals + 2*2 (scam) + 2*1 (spam) = 9
    assert len(out) == 9
    assert counts["normal"] == 1
    assert counts["scam"] == 6
    assert counts["spam"] == 3


def test_class_distribution():
    counts = class_distribution(
        [("normal", "x", "y"), ("scam", "a", "b"), ("scam", "c", "d")]
    )
    assert counts == {"normal": 1, "scam": 2}


def test_ab_config_from_env_defaults(monkeypatch):
    monkeypatch.delenv("AB_TEST_ENABLED", raising=False)
    monkeypatch.delenv("AB_TEST_CHALLENGER", raising=False)
    cfg = ABConfig.from_env()
    assert cfg.enabled is False
    assert cfg.challenger_version is None
    assert cfg.weight_b == 0.2


def test_ab_config_from_env_enabled(monkeypatch):
    monkeypatch.setenv("AB_TEST_ENABLED", "true")
    monkeypatch.setenv("AB_TEST_CHALLENGER", "v2")
    monkeypatch.setenv("AB_TEST_WEIGHT_B", "0.7")
    cfg = ABConfig.from_env()
    assert cfg.enabled is True
    assert cfg.challenger_version == "v2"
    assert cfg.weight_b == 0.7


def test_ab_tester_routes_only_to_a_when_disabled():
    tester = ABTester(predict_a=lambda: {"a": 1})
    assert tester.is_active() is False
    for _ in range(50):
        result = __import__("asyncio").run(tester.predict())
        assert result.bucket == "A"


def test_ab_tester_splits_traffic_when_enabled():
    seen: list[str] = []

    def a():
        return {"version": "a"}

    def b():
        return {"version": "b"}

    tester = ABTester(predict_a=a, predict_b=b, config=ABConfig(True, "v2", 0.5))
    assert tester.is_active()
    # 200 trials; both buckets should be picked with ~equal frequency
    import asyncio

    for _ in range(200):
        result = asyncio.run(tester.predict())
        seen.append(result.bucket)
    assert "A" in seen and "B" in seen
    counts = Counter(seen)
    assert 60 < counts["A"] < 140  # ~50% give or take


def test_make_default_tester_helper(monkeypatch):
    monkeypatch.delenv("AB_TEST_ENABLED", raising=False)
    tester = make_default_tester(predict_active=lambda: {}, predict_challenger=lambda: {})
    assert tester.is_active() is False