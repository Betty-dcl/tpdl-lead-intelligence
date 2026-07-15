"""Bouncer connector for Inès — email deliverability verification.

Runs BEFORE any send: only "deliverable" emails should reach a sequence
(roadmap criterion: 100% of emails pass Bouncer). `is_configured()` gates on
BOUNCER_API_KEY so Inès can explain the step instead of erroring when absent.

Constitution: never fabricate a verdict. No key ⇒ raise BouncerNotConfigured;
an API/parse error ⇒ return status "unknown" with deliverable=False (fail
closed — an unverified address is never treated as safe to send). Dormant (zero
network, zero cost) until BOUNCER_API_KEY lands in .env.
"""
from __future__ import annotations

import logging

from app.config import settings

logger = logging.getLogger(__name__)

# Bouncer statuses → our normalised buckets. Only "deliverable" is safe to send.
_STATUS_MAP = {
    "deliverable": "deliverable",
    "risky": "risky",
    "undeliverable": "undeliverable",
    "unknown": "unknown",
}


class BouncerNotConfigured(RuntimeError):
    pass


def is_configured() -> bool:
    return bool(settings.bouncer_api_key)


def _unknown(email: str, reason: str) -> dict:
    """Fail-closed verdict: never mark an unverified address deliverable."""
    return {"email": email, "status": "unknown", "deliverable": False, "reason": reason}


def verify_email(email: str) -> dict:
    """Return {email, status, deliverable, reason} for one address.

    status ∈ deliverable | risky | undeliverable | unknown.
    deliverable is True ONLY for status == "deliverable".
    Raises BouncerNotConfigured when no key is set (the availability gate).
    Never raises on an API error — returns a fail-closed "unknown" verdict.
    """
    if not is_configured():
        raise BouncerNotConfigured(
            "BOUNCER_API_KEY is not set — add it to .env to enable email verification."
        )
    import json
    import urllib.error
    import urllib.parse
    import urllib.request

    url = ("https://api.usebouncer.com/v1.1/email/verify?"
           + urllib.parse.urlencode({"email": email}))
    req = urllib.request.Request(
        url, headers={"x-api-key": settings.bouncer_api_key}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        logger.warning("[bouncer] %s verify failed: HTTP %s", email, exc.code)
        return _unknown(email, f"http_{exc.code}")
    except Exception as exc:  # network / parse — never crash the caller
        logger.warning("[bouncer] %s verify error: %s", email, exc)
        return _unknown(email, "request_error")

    status = _STATUS_MAP.get((data.get("status") or "").lower(), "unknown")
    return {
        "email": email,
        "status": status,
        "deliverable": status == "deliverable",
        "reason": data.get("reason") or None,
    }


def verify_many(emails: list[str]) -> list[dict]:
    """Verify a batch, one call each. Returns one verdict dict per input email."""
    return [verify_email(e) for e in emails]
