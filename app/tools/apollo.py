"""Apollo.io connector for Inès — decision-maker contact enrichment.

Stubbed until TPDL provides APOLLO_API_KEY. `is_configured()` lets the agent
degrade gracefully (explain what it WOULD fetch) instead of erroring when the
key is absent. The real `people/search` call goes in `fetch_contacts` once the
key is in.
"""
from __future__ import annotations

import logging

from app.config import settings

logger = logging.getLogger(__name__)

# Decision-maker titles Inès targets by default.
DEFAULT_TITLES = ("CEO", "Chief Executive Officer",
                  "CTO", "Chief Technology Officer",
                  "CFO", "Chief Financial Officer")

# Signal-driven targeting (Inès prompt §3): the company's lead signal points at
# WHICH decision-makers matter — not a generic CEO/CTO/CFO pull for everyone.
SIGNAL_TITLES: dict[str, tuple[str, ...]] = {
    "leadership_change": ("CEO", "COO", "CMO", "Chief Commercial Officer"),
    "hiring":            ("VP Sales", "Head of Digital", "Head of Data",
                          "Chief Commercial Officer"),
    "ma_expansion":      ("COO", "CIO", "CTO", "Head of Commercial Operations"),
    "pe_event":          ("CEO", "CFO"),
    "digital_initiative": ("Chief Digital Officer", "CTO", "CIO",
                           "Head of Transformation"),
    "org_restructuring": ("COO", "CTO", "Chief Commercial Officer"),
}


def titles_for_signal(lead_signal: str | None) -> tuple[str, ...]:
    """Which titles to prioritise given the company's lead signal category.

    Falls back to the baseline C-suite when the signal is unknown. Used both
    to describe the target persona set (Mode A) and to parametrise the live
    Apollo people/search (Mode B) once the key is wired."""
    if lead_signal and lead_signal in SIGNAL_TITLES:
        return SIGNAL_TITLES[lead_signal]
    return DEFAULT_TITLES


class ApolloNotConfigured(RuntimeError):
    pass


def is_configured() -> bool:
    return bool(settings.apollo_api_key)


def fetch_contacts(company_name: str, titles: tuple[str, ...] = DEFAULT_TITLES) -> list[dict]:
    """Return [{full_name, title, email, linkedin_url, location}] for a company.

    Raises ApolloNotConfigured when no key is set (the money/availability gate).
    Live call: POST https://api.apollo.io/v1/mixed_people/search with the
    X-Api-Key header, filtered on the organisation name + the signal-driven
    person_titles. Never raises on an API error — returns [] so Inès degrades
    gracefully rather than crashing a batch.

    NOTE (confirm on first live use): Apollo's search may return an
    email-unlocked placeholder ("email_not_unlocked@domain.com") on some plans;
    revealing the real email can need a separate enrichment call / plan tier.
    Inès stores whatever comes back and flags missing emails downstream.
    """
    if not is_configured():
        raise ApolloNotConfigured(
            "APOLLO_API_KEY is not set — add it to .env to enable contact pulls."
        )
    import json
    import urllib.error
    import urllib.request

    payload = {
        "organization_names": [company_name],
        "person_titles": list(titles),
        "per_page": 10,
    }
    req = urllib.request.Request(
        "https://api.apollo.io/v1/mixed_people/search",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "X-Api-Key": settings.apollo_api_key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        logger.warning("[apollo] %s search failed: HTTP %s", company_name, exc.code)
        return []
    except Exception as exc:  # network / parse — never crash the caller
        logger.warning("[apollo] %s search error: %s", company_name, exc)
        return []

    return [_person(p) for p in (data.get("people") or [])]


def _person(p: dict) -> dict:
    name = p.get("name") or " ".join(
        x for x in (p.get("first_name"), p.get("last_name")) if x).strip()
    location = ", ".join(x for x in (p.get("city"), p.get("state"), p.get("country")) if x)
    return {
        "full_name": name or "Unknown",
        "title": p.get("title"),
        "email": p.get("email"),
        "linkedin_url": p.get("linkedin_url"),
        "location": location or None,
    }
