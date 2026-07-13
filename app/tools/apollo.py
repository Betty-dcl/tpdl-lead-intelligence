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


class ApolloNotConfigured(RuntimeError):
    pass


def is_configured() -> bool:
    return bool(settings.apollo_api_key)


def fetch_contacts(company_name: str, titles: tuple[str, ...] = DEFAULT_TITLES) -> list[dict]:
    """Return [{full_name, title, email, linkedin_url, location}] for a company.

    Raises ApolloNotConfigured when no key is set — the caller decides how to
    surface that. The live Apollo `people/search` request is wired here once the
    key arrives (POST https://api.apollo.io/v1/mixed_people/search, header
    X-Api-Key, filter on organization name + person_titles).
    """
    if not is_configured():
        raise ApolloNotConfigured(
            "APOLLO_API_KEY is not set — add it to .env to enable contact pulls."
        )
    # TODO(form-ines): real Apollo people/search call once the key is provided.
    logger.warning("[apollo] key present but live fetch not yet implemented")
    return []
