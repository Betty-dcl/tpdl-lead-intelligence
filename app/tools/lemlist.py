"""Lemlist connector for Julie — multichannel outreach sequences.

Julie drafts the message; Lemlist enrols the (verified) lead into an email /
LinkedIn sequence. `is_configured()` gates on LEMLIST_API_KEY.

⚠️ OUTBOUND SIDE-EFFECT: `add_lead_to_campaign` enrols a real person into a real
sending sequence. It is therefore NOT called automatically anywhere — a human
must trigger it after approving the draft (Premium 5 stay with Andrés; other
sends go through the SDR). This module only provides the gated client; wiring it
to an endpoint or agent action is a separate, deliberate step.

Constitution / safety: never fabricate a result; fail closed. No key ⇒ raise
LemlistNotConfigured. An API error returns {ok: False, ...} (never a fake
success). `list_campaigns` is the safe read used to discover campaign ids.
Dormant (zero network, zero cost) until LEMLIST_API_KEY lands in .env.
"""
from __future__ import annotations

import base64
import logging

from app.config import settings

logger = logging.getLogger(__name__)

_BASE = "https://api.lemlist.com/api"


class LemlistNotConfigured(RuntimeError):
    pass


def is_configured() -> bool:
    return bool(settings.lemlist_api_key)


def _auth_header() -> dict:
    # Lemlist uses HTTP Basic auth with the API key as the password (empty user).
    token = base64.b64encode(f":{settings.lemlist_api_key}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def _require() -> None:
    if not is_configured():
        raise LemlistNotConfigured(
            "LEMLIST_API_KEY is not set — add it to .env to enable Lemlist sequences."
        )


def list_campaigns() -> list[dict]:
    """Safe READ: list campaigns [{id, name}]. Returns [] on error (never fabricates)."""
    _require()
    import json
    import urllib.error
    import urllib.request

    req = urllib.request.Request(
        f"{_BASE}/campaigns", headers=_auth_header(), method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        logger.warning("[lemlist] list_campaigns failed: HTTP %s", exc.code)
        return []
    except Exception as exc:  # network / parse — never crash the caller
        logger.warning("[lemlist] list_campaigns error: %s", exc)
        return []
    rows = data if isinstance(data, list) else data.get("campaigns", [])
    return [{"id": c.get("_id") or c.get("id"), "name": c.get("name")} for c in rows]


def add_lead_to_campaign(campaign_id: str, email: str,
                         first_name: str | None = None,
                         last_name: str | None = None,
                         company_name: str | None = None,
                         extra: dict | None = None) -> dict:
    """⚠️ OUTBOUND: enrol a lead into a Lemlist campaign (starts a real sequence).

    Call this ONLY after a human has approved the draft AND the email passed
    Bouncer (`bouncer.verify_email(...)['deliverable'] is True`). Returns
    {ok, email, campaign_id, detail}. On any API error returns ok=False — it
    never reports a send that did not happen.
    """
    _require()
    import json
    import urllib.error
    import urllib.parse
    import urllib.request

    body = {"email": email}
    if first_name:
        body["firstName"] = first_name
    if last_name:
        body["lastName"] = last_name
    if company_name:
        body["companyName"] = company_name
    if extra:
        body.update(extra)

    url = f"{_BASE}/campaigns/{campaign_id}/leads/{urllib.parse.quote(email)}"
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", **_auth_header()},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        logger.warning("[lemlist] add lead %s failed: HTTP %s", email, exc.code)
        return {"ok": False, "email": email, "campaign_id": campaign_id,
                "detail": f"http_{exc.code}"}
    except Exception as exc:  # network / parse — never crash the caller
        logger.warning("[lemlist] add lead %s error: %s", email, exc)
        return {"ok": False, "email": email, "campaign_id": campaign_id,
                "detail": "request_error"}
    return {"ok": True, "email": email, "campaign_id": campaign_id, "detail": data}
