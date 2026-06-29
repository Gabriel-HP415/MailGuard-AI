"""URL extraction and risk analysis."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

from ai_service.app.constants import SUSPICIOUS_TLDS, URL_SHORTENERS

_URL_RE = re.compile(r"https?://[^\s<>\"']+|www\.[^\s<>\"']+", re.IGNORECASE)


@dataclass
class UrlAnalysis:
    """Risk assessment for a single URL."""

    url: str
    domain: str
    is_shortener: bool
    has_ip_address: bool
    suspicious_tld: bool
    has_at_symbol: bool
    has_punycode: bool
    is_https: bool
    num_dots: int
    num_hyphens: int
    risk_score: float
    reasons: list[str]


def _domain_of(url: str) -> str:
    """Extract the host portion of a URL string."""
    parsed = urlparse(url if "://" in url else f"http://{url}")
    return (parsed.netloc or "").lower().split("@")[-1].split(":")[0]


def _looks_like_ip(host: str) -> bool:
    return bool(re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", host))


def extract_links(text: str) -> list[str]:
    """Return the list of HTTP(S) URLs found in a string."""
    if not text:
        return []
    return [m.group(0).rstrip(".,;:!?\"')]}>") for m in _URL_RE.finditer(text)]


def analyze_url(url: str) -> UrlAnalysis:
    """Compute a 0-100 risk score for a single URL."""
    reasons: list[str] = []
    score = 0.0

    domain = _domain_of(url)
    is_shortener = domain in URL_SHORTENERS
    is_ip = _looks_like_ip(domain)
    punycode = "xn--" in domain
    at_in_url = "@" in url
    https = url.lower().startswith("https://")
    tld = "." + domain.rsplit(".", 1)[-1] if "." in domain else ""
    suspicious_tld = tld in SUSPICIOUS_TLDS
    num_dots = domain.count(".")
    num_hyphens = domain.count("-")

    if is_shortener:
        score += 20
        reasons.append("URL shortener hides destination")
    if is_ip:
        score += 30
        reasons.append("IP address used instead of domain")
    if punycode:
        score += 20
        reasons.append("Punycode (possible homograph attack)")
    if at_in_url:
        score += 25
        reasons.append("'@' symbol in URL")
    if suspicious_tld:
        score += 15
        reasons.append(f"Suspicious TLD: {tld}")
    if not https:
        score += 5
        reasons.append("Plain HTTP (no encryption)")
    if num_dots >= 4:
        score += 10
        reasons.append("Excessive subdomains")
    if num_hyphens >= 3:
        score += 10
        reasons.append("Many hyphens in domain")

    return UrlAnalysis(
        url=url,
        domain=domain,
        is_shortener=is_shortener,
        has_ip_address=is_ip,
        suspicious_tld=suspicious_tld,
        has_at_symbol=at_in_url,
        has_punycode=punycode,
        is_https=https,
        num_dots=num_dots,
        num_hyphens=num_hyphens,
        risk_score=min(100.0, score),
        reasons=reasons,
    )