"""HTTP client for the AI Service.

Dispatches between providers based on ``settings.ai_provider``:

* ``gemini`` — calls Google Gemini directly (recommended for cloud).
* ``http``   — calls an external AI service over HTTP (legacy default).
* ``local``  — placeholder; real local model lives in ai_service/.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings
from app.schemas.prediction import PredictionRequest

logger = logging.getLogger(__name__)


class AIServiceError(AppError := __import__("app.api.errors", fromlist=["AppError"]).AppError):
    """Raised when the AI Service fails to respond."""


_DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=5.0)


_SUSPICIOUS_TOKENS = (
    "verify", "urgent", "click here", "password", "suspended", "limit",
    "won", "winner", "prize", "bit.ly", "tinyurl", ".tk", ".xyz",
    # Account action keywords
    "unauthorized", "sign-in", "suspicious", "compromised", "locked",
    "verify your", "confirm your", "update your", "validate your",
    "account update", "security alert", "unusual activity", "unrecognized",
    "immediately", "within 24", "within 12", "within 48",
    # Financial / payment
    "payment", "credit card", "debit card", "bank account", "ssn",
    "social security", "tax id", "routing number",
    # Threat language
    "permanent", "terminated", "close your account", "will be closed",
    "suspended permanently", "limited access", "restricted",
    "action required", "confirm identity", "identity verification",
    # Claim / prize
    "you have won", "you've won", "claim your", "claim now",
    # Fake urgency
    "expires today", "today only", "last chance", "limited time",
    "offer expires", "act now", "do not ignore",
    # Credential harvesting
    "enter your", "input your", "provide your", "update now",
    "login attempt", "new device", "unusual sign-in",
)

# Brand names commonly impersonated — if seen in a suspicious URL subdomain
_BRAND_KEYWORDS = {
    "paypal": "paypal",
    "apple": "apple", "appleid": "apple",
    "google": "google", "googledrive": "google",
    "microsoft": "microsoft", "outlook": "microsoft",
    "amazon": "amazon", "aws": "amazon",
    "facebook": "facebook", "meta": "facebook",
    "instagram": "instagram",
    "netflix": "netflix",
    "ebay": "ebay",
    "bank": "bank", "chase": "chase", "wellsfargo": "wells fargo",
    "citi": "citi", "bankofamerica": "bank of america",
    "dropbox": "dropbox",
    "linkedin": "linkedin",
    "steam": "steam",
    "spotify": "spotify",
    "coinbase": "coinbase", "binance": "binance",
}


def _is_typosquatting_url(url: str, sender_domain: str = "") -> bool:
    """Return True if `url` looks like a phishing/toposquatting site.

    Strategy:
    - If `sender_domain` is provided, flag the URL if it differs from the
      legitimate sender domain (e.g. sender=paypal.com, url=paypal-secure.com).
    - Otherwise, flag URLs whose registered domain contains a brand keyword
      but is not the genuine brand domain.

    E.g.:
      sender=paypal.com, url=paypal-secure.com/login  -> True  (sender mismatch)
      url=secure-update-paypal-verify.com/login        -> True  (brand in domain, not real TLD)
      url=paypal.com/confirm-identity                   -> False (legitimate)
      url=apple.com-verify-id.net/secure-login         -> True  (apple in domain, not .com/.apple)
    """
    import re
    if not url:
        return False
    url_lower = url.lower()

    # Strategy 1: Sender domain mismatch — strongest signal.
    # If sender claims to be @paypal.com but URL goes elsewhere, it's phishing.
    if sender_domain:
        sender_clean = sender_domain.strip().lower()
        url_match = re.match(r"https?://([^/:]+)", url_lower)
        if url_match:
            url_domain = url_match.group(1)
            # Extract the registered domain (last 2 parts typically)
            # For "paypal-secure.com" -> "paypal-secure.com"
            # For "secure.paypal.com" -> "paypal.com"
            url_parts = url_domain.split(".")
            if len(url_parts) >= 2:
                # Get the last two parts as the "registered domain"
                url_registered = ".".join(url_parts[-2:])
                # If sender domain is a known brand TLD and URL doesn't match, flag
                if url_registered != sender_clean and sender_clean in {
                        "paypal.com", "apple.com", "google.com", "microsoft.com",
                        "amazon.com", "facebook.com", "instagram.com", "netflix.com",
                        "ebay.com", "dropbox.com", "linkedin.com", "steamcommunity.com",
                        "spotify.com", "coinbase.com", "binance.com",
                        "chase.com", "wellsfargo.com", "bankofamerica.com", "citi.com",
                        "outlook.com", "live.com", "appleid.apple.com",
                }:
                    return True

    # Strategy 2: Domain contains brand keyword but is NOT a known real brand domain.
    # Build the full domain (all parts) to check.
    match = re.match(r"https?://([^/:]+)", url_lower)
    if not match:
        return False
    full_domain = match.group(1)  # e.g. "secure-update-paypal-verify.com"

    # Known legitimate brand domains (registered domain = brand + safe TLD)
    safe_brand_registered = {
        # brand keyword -> set of legitimate registered domains
        "paypal":       {"paypal.com"},
        "apple":        {"apple.com", "appleid.apple.com"},
        "google":       {"google.com", "goo.gl"},
        "microsoft":    {"microsoft.com"},
        "outlook":      {"outlook.com", "live.com"},
        "amazon":       {"amazon.com", "amazon.co.uk", "amazon.de", "aws.amazon.com"},
        "facebook":     {"facebook.com", "fb.com"},
        "instagram":    {"instagram.com"},
        "netflix":      {"netflix.com"},
        "ebay":         {"ebay.com"},
        "dropbox":      {"dropbox.com"},
        "linkedin":     {"linkedin.com"},
        "steam":        {"steamcommunity.com", "steampowered.com"},
        "spotify":      {"spotify.com"},
        "coinbase":     {"coinbase.com"},
        "binance":      {"binance.com"},
        "chase":        {"chase.com"},
        "wellsfargo":   {"wellsfargo.com"},
        "bankofamerica":{"bankofamerica.com"},
        "citi":         {"citi.com"},
    }

    # Strip common path/query from domain for checking
    # (domain is already extracted from URL regex above)

    # If the full domain is in our safe list, it's legitimate
    if full_domain in {d for ds in safe_brand_registered.values() for d in ds}:
        return False

    # Check if the registered domain (last 2 parts) contains a brand keyword
    domain_parts = full_domain.split(".")
    registered = ".".join(domain_parts[-2:])  # last 2 parts

    for kw, legitimate_domains in safe_brand_registered.items():
        if kw in registered:
            # It's a brand keyword in the domain — is it the REAL domain?
            if registered not in legitimate_domains:
                return True  # typosquatting
            # It's the real domain (e.g. paypal.com) — legitimate
            return False

    return False


def _stub_prediction(payload: PredictionRequest) -> dict[str, Any]:
    """Deterministic rule-based stand-in for the AI service.

    Used in local dev (`AI_PROVIDER=stub`) so the backend can be exercised
    end-to-end without an external AI process or API key. The output shape
    matches what `predict_service.save_prediction` expects from the AI.
    """
    import hashlib
    import random
    import re
    import urllib.parse

    sender = (payload.email.sender or "").lower()
    subject = (payload.email.subject or "").lower()
    body = (payload.email.body_text or payload.email.body_html or "").lower()
    links: list[str] = payload.email.links or []

    # --- Extract sender domain EARLY (needed for URL checks) ---
    try:
        sender_domain = sender.split("@")[1] if "@" in sender else ""
        sender_domain = sender_domain.split(">")[0].strip()
    except Exception:
        sender_domain = ""

    text = " ".join((sender, subject, body))
    hits = [tok for tok in _SUSPICIOUS_TOKENS if tok in text]

    # --- Detect typosquatting URLs ---
    suspicious_urls = []
    for raw_url in links:
        url_lower = raw_url.lower()
        if _is_typosquatting_url(url_lower, sender_domain):
            suspicious_urls.append({"url": raw_url, "score": 0.95, "reason": "typosquatting"})
        elif any(s in url_lower for s in ["bit.ly", "tinyurl", ".tk", ".xyz", "goo.gl"]):
            suspicious_urls.append({"url": raw_url, "score": 0.85, "reason": "suspicious_shortener"})
        elif not url_lower.startswith("https://"):
            suspicious_urls.append({"url": raw_url, "score": 0.6, "reason": "non_https"})

    # If no links provided, scan body for URL-like strings
    if not suspicious_urls:
        url_pattern = re.compile(r"https?://[^\s<>\"')\]]+", re.IGNORECASE)
        found_urls = url_pattern.findall(body)
        for raw_url in found_urls:
            if _is_typosquatting_url(raw_url, sender_domain):
                suspicious_urls.append({"url": raw_url, "score": 0.95, "reason": "typosquatting_in_body"})
            elif any(s in raw_url.lower() for s in ["bit.ly", "tinyurl", ".tk", ".xyz"]):
                suspicious_urls.append({"url": raw_url, "score": 0.85, "reason": "suspicious_shortener"})

    # --- Sender domain check ---
    # Check if sender domain impersonates a known brand
    safe_brand_domains_for_sender = {
        "paypal.com", "apple.com", "appleid.apple.com",
        "google.com", "microsoft.com", "amazon.com",
        "facebook.com", "instagram.com", "netflix.com",
        "ebay.com", "dropbox.com", "linkedin.com",
        "steamcommunity.com", "spotify.com",
        "coinbase.com", "binance.com",
        "chase.com", "wellsfargo.com", "bankofamerica.com", "citi.com",
        "outlook.com", "live.com",
    }

    safe_domains = {
        "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
        "company.com", "corp.com", "enterprise.com",
        "mailguard.ai", "paypal.com", "apple.com", "amazon.com",
        "microsoft.com", "google.com", "facebook.com", "netflix.com",
    }
    sender_is_safe = sender_domain in safe_domains

    # --- Compute risk score ---
    # Start with token hits
    risk = min(100.0, 8.0 * len(hits) + 5.0)

    # URL factors
    risk += 30 * len(suspicious_urls) if suspicious_urls else 0

    # Sender impersonation: sender claims brand domain but isn't legitimate
    # e.g. sender=support@paypal-secure.com but sender_domain is not in safe brand list
    sender_is_suspicious = bool(
        sender_domain
        and sender_domain not in safe_brand_domains_for_sender
        and any(brand in sender_domain for brand in ["paypal", "apple", "google",
                  "microsoft", "amazon", "facebook", "instagram", "netflix",
                  "ebay", "dropbox", "steam", "spotify", "coinbase", "binance"])
    )
    if sender_is_suspicious:
        risk += 25
        hits.append(f"sender_domain:{sender_domain}")

    # Brand safety bonus: if sender is a known legitimate brand domain
    # AND no typosquatting URLs were found, the email is likely a real
    # security notification (e.g. PayPal real security alerts). Reduce risk.
    if sender_domain in safe_brand_domains_for_sender and not suspicious_urls:
        # Real brand emails from legitimate senders are safe by default.
        # Only re-activate a small amount of risk for multiple tokens.
        risk = min(25, 4.0 * len(hits))  # At most 25 risk for word-heavy real alerts

    # Brand impersonation in subject line (without matching sender)
    brand_keywords = ["paypal", "apple", "google", "microsoft", "amazon", "facebook",
                      "instagram", "netflix", "ebay", "dropbox", "steam", "spotify"]
    subject_brands = [b for b in brand_keywords if b in subject]
    if subject_brands and not sender_is_safe:
        risk += 20
        hits.append(f"subject_brand:{subject_brands[0]}")

    # Cap at 100
    risk = min(100.0, risk)

    # is_phish drives the class prediction
    is_phish = risk >= 50

    pred_class = "scam" if is_phish else "normal"
    confidence = round(0.55 + min(0.4, risk / 250.0), 3)

    # Deterministic seed so the same email -> same response
    seed = int(hashlib.md5(text.encode("utf-8")).hexdigest(), 16) % (2 ** 31)
    rng = random.Random(seed)
    # Order matches constants.INDEX_TO_CLASS: normal, notification, spam, scam
    p_normal = round(rng.uniform(0.05, 0.4), 3)
    p_notif = round(rng.uniform(0.02, 0.15), 3)
    p_spam = round(rng.uniform(0.05, 0.3), 3)
    p_scam_base = 0.25 if is_phish else 0.02
    p_scam = round(min(0.95, p_scam_base + risk / 200.0), 3)

    total = p_normal + p_notif + p_spam + p_scam
    probs_dict = {
        "normal": round(p_normal / total, 4),
        "notification": round(p_notif / total, 4),
        "spam": round(p_spam / total, 4),
        "scam": round(p_scam / total, 4),
    }

    # Map to internal class enum names
    class_enum = "scam" if is_phish else "normal"

    if risk >= 75:
        threat = "critical"
    elif risk >= 50:
        threat = "high"
    elif risk >= 25:
        threat = "medium"
    else:
        threat = "low"

    return {
        "predicted_class": class_enum,
        "class_index": 3 if is_phish else 0,
        "confidence": confidence,
        "risk_score": round(risk, 2),
        "threat_level": threat,
        "probabilities": probs_dict,
        "suspicious_urls": suspicious_urls,
        "explanation": (
            {"matched_signals": hits, "note": "stub classifier"}
            if hits else None
        ),
        "model_version": "stub-v2",
    }


def _email_to_gemini_inputs(payload: PredictionRequest) -> tuple[str, str, str]:
    """Map a PredictionRequest to (sender, subject, body) for Gemini."""
    email = payload.email
    sender = email.sender or ""
    subject = email.subject or ""
    body = email.body_text or email.body_html or ""
    return sender, subject, body


class AIServiceClient:
    """Async client wrapping the configured AI provider."""

    def __init__(self, base_url: str | None = None, timeout: httpx.Timeout | None = None):
        self.provider = settings.ai_provider.lower()
        self.base_url = (base_url or settings.ai_service_url).rstrip("/")
        self.timeout = timeout or _DEFAULT_TIMEOUT

    async def predict(self, payload: PredictionRequest) -> dict[str, Any]:
        if self.provider == "gemini":
            from app.services.gemini_classifier import get_gemini_classifier

            sender, subject, body = _email_to_gemini_inputs(payload)
            try:
                return await get_gemini_classifier().classify(sender, subject, body)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Gemini classification failed")
                raise AIServiceError(message=f"Gemini classification failed: {exc}") from exc

        if self.provider == "stub":
            # Local dev shortcut: deterministic stub classifier. Lets the API
            # exercise end-to-end without an external AI service or API key.
            return _stub_prediction(payload)

        # Legacy: HTTP-based AI service
        from app.api.errors import AppError

        url = f"{self.base_url}/predict"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Convert datetime objects to ISO strings for JSON serialization
                payload_dict = payload.model_dump()
                for key, value in payload_dict.items():
                    if hasattr(value, 'isoformat'):
                        payload_dict[key] = value.isoformat()
                
                # Map backend email fields to AI service format
                email_data = payload_dict.get('email', {})
                ai_payload = {
                    'subject': email_data.get('subject', ''),
                    'body': email_data.get('body_text') or email_data.get('body_html') or '',
                    'sender': email_data.get('sender', ''),
                    'sender_domain': email_data.get('sender_domain'),
                    'links': email_data.get('links'),
                }
                resp = await client.post(url, json=ai_payload)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error("AI service error: %s - %s", exc.response.status_code, exc.response.text)
            raise AppError(
                message=f"AI service returned {exc.response.status_code}",
                details={"body": exc.response.text[:500]},
            ) from exc
        except httpx.RequestError as exc:
            logger.error("AI service unreachable: %s", exc)
            raise AppError(message="AI service unreachable") from exc

    async def predict_batch(self, payloads: list[PredictionRequest]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for p in payloads:
            results.append(await self.predict(p))
        return results

    async def health(self) -> dict[str, Any]:
        """Return a liveness dict that reflects the configured provider."""
        if self.provider == "gemini":
            from app.services.gemini_classifier import get_gemini_classifier

            try:
                get_gemini_classifier()  # raises if key missing
                return {
                    "status": "ok",
                    "provider": "gemini",
                    "model": settings.gemini_model,
                }
            except Exception as exc:  # noqa: BLE001
                return {"status": "degraded", "provider": "gemini", "error": str(exc)}

        url = f"{self.base_url}/health"
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
        except httpx.RequestError as exc:
            return {"status": "unreachable", "error": str(exc)}


ai_client = AIServiceClient()