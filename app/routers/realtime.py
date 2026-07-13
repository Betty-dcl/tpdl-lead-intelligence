"""Realtime config — exposes the PUBLIC Supabase URL + anon key to the frontend.

Only the anon (public) key is exposed here. The service_role key NEVER leaves
the server. If Supabase isn't configured, returns enabled=false and the
frontend keeps polling/refreshing as before.
"""
from fastapi import APIRouter

from app.config import settings

router = APIRouter(prefix="/api/realtime", tags=["realtime"])


@router.get("/config")
def realtime_config() -> dict:
    return {
        "enabled":  bool(settings.supabase_url and settings.supabase_anon_key),
        "url":      settings.supabase_url or None,
        "anon_key": settings.supabase_anon_key or None,  # public by design
    }
