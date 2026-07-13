"""Veille API — manual trigger + status."""
import logging
from fastapi import APIRouter
from app.tools.memory import get_memory

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/veille", tags=["veille"])


@router.post("/run")
def trigger_veille() -> dict:
    """Trigger Iris veille manually (same job as the Monday scheduler)."""
    from app.scheduler import run_veille
    return run_veille()


@router.get("/last")
def last_veille() -> dict:
    mem = get_memory()
    runs = mem.get("veille_runs", [])
    if not runs:
        return {"status": "never_run", "subjects": []}
    latest = runs[0]
    return {"status": "ok", **latest}


@router.get("/history")
def veille_history() -> list[dict]:
    mem = get_memory()
    return mem.get("veille_runs", [])
