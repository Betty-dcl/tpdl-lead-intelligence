"""Supabase client — server-side, uses the service_role key (bypasses RLS).

Activates only when SUPABASE_URL + SUPABASE_SERVICE_KEY are set.
When unset, `get_supabase()` returns None and the app keeps using SQLite.
"""
import logging
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

_client = None  # cached singleton


def get_supabase():
    """Return a service-role Supabase client, or None if not configured."""
    global _client
    if not settings.supabase_enabled:
        return None
    if _client is None:
        try:
            from supabase import create_client
            _client = create_client(
                settings.supabase_url,
                settings.supabase_service_key,
            )
            logger.info("[supabase] client initialised (service_role)")
        except Exception as exc:
            logger.exception("[supabase] failed to initialise: %s", exc)
            return None
    return _client


def is_enabled() -> bool:
    return settings.supabase_enabled
