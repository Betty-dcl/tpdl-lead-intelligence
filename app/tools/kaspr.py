"""Kaspr connector for Inès — decision-maker contact enrichment (target engine).

Kaspr replaces Apollo (roadmap: better CH/ES coverage). Deliberately a DROP-IN
for `apollo.fetch_contacts`: same return shape
`[{full_name, title, email, linkedin_url, location}]`, same graceful-degradation
contract. `is_configured()` gates on KASPR_API_KEY so Inès can explain what she
WOULD fetch instead of erroring when the key is absent.

Constitution: never fabricate a contact. No key ⇒ raise KasprNotConfigured;
an API/parse error ⇒ return [] (never invent people). The exact request/response
shape is confirmed on first live use — Kaspr's API is key-gated, so this stays
dormant (zero network, zero cost) until KASPR_API_KEY lands in .env.
"""
from __future__ import annotations

import logging

from app.config import settings

# Reuse Inès's signal→titles targeting so Kaspr and Apollo pull the same personas.
from app.tools.apollo import DEFAULT_TITLES, titles_for_signal  # noqa: F401 (re-exported)

logger = logging.getLogger(__name__)


class KasprNotConfigured(RuntimeError):
    pass


def is_configured() -> bool:
    return bool(settings.kaspr_api_key)


def fetch_contacts(company_name: str, titles: tuple[str, ...] = DEFAULT_TITLES) -> list[dict]:
    """Return [{full_name, title, email, linkedin_url, location}] for a company.

    Raises KasprNotConfigured when no key is set (the availability gate).
    Never raises on an API error — returns [] so Inès degrades gracefully
    rather than crashing a batch. Same contract as apollo.fetch_contacts.
    """
    if not is_configured():
        raise KasprNotConfigured(
            "KASPR_API_KEY is not set — add it to .env to enable Kaspr contact pulls."
        )
    import json
    import urllib.error
    import urllib.request

    # Confirm the exact endpoint/payload on first live use (Kaspr B2B API).
    payload = {
        "organization": company_name,
        "jobTitles": list(titles),
        "limit": 10,
    }
    req = urllib.request.Request(
        "https://api.kaspr.io/v1/people/search",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.kaspr_api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        logger.warning("[kaspr] %s search failed: HTTP %s", company_name, exc.code)
        return []
    except Exception as exc:  # network / parse — never crash the caller
        logger.warning("[kaspr] %s search error: %s", company_name, exc)
        return []

    people = data.get("people") or data.get("results") or []
    return [_person(p) for p in people]


def _person(p: dict) -> dict:
    name = p.get("name") or " ".join(
        x for x in (p.get("firstName"), p.get("lastName")) if x).strip()
    emails = p.get("emails") or ([p["email"]] if p.get("email") else [])
    location = ", ".join(
        x for x in (p.get("city"), p.get("region"), p.get("country")) if x)
    return {
        "full_name": name or "Unknown",
        "title": p.get("jobTitle") or p.get("title"),
        "email": emails[0] if emails else None,
        "linkedin_url": p.get("linkedinUrl") or p.get("linkedin_url"),
        "location": location or None,
    }
