"""Lead-intelligence engine trigger — run the pipeline from the dashboard.

Connects the two halves of the system: instead of dropping to a terminal
(`python -m pipeline.runner …`), the team can kick a run from the UI.

Safety (non-negotiable):
- **Dry-run** (default) runs the probe fixture through the real engine
  (research → extract → score) at ZERO cost and returns the scored preview.
  It NEVER writes to the `companies` table — mock dry-run scores must never
  overwrite the frozen 25/05 reference data.
- **Live** (`live=true`) spends money and needs ANTHROPIC_API_KEY. Gated: without
  the key the endpoint refuses with a clear message (see go-live-runbook.md).
  A live run's real scores DO get imported (that is the whole point) — handled
  by import_csv.py, out of band, so this endpoint stays read-only for the DB.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/engine", tags=["engine"])

_FIXTURE = Path(__file__).resolve().parent.parent.parent / "pipeline" / "fixtures" / "probe_diagnostics.json"

# last dry-run summary, kept in memory so the UI can show "last smoke test"
_last_run: dict | None = None


class EngineRunRequest(BaseModel):
    live: bool = False


def _anthropic_ready() -> bool:
    return bool(settings.anthropic_api_key) and settings.anthropic_api_key != "not-set"


@router.get("/status")
def engine_status() -> dict:
    """What the engine can do right now (drives the UI panel)."""
    from pipeline import estimate as est_mod
    est = est_mod.estimate_run(1)
    return {
        "dry_run_available": True,          # always — zero cost
        "live_available": _anthropic_ready(),
        "live_blocker": None if _anthropic_ready() else "ANTHROPIC_API_KEY not set",
        "per_company_usd": round(est.per_company_usd, 4),
        "reference_run": "2026-05-25 (492 companies, 35 outreach-eligible) — frozen",
        "last_dry_run": _last_run,
        "note": ("Dry-run is a zero-cost smoke test on the probe fixture and never "
                 "touches the scored database. A live run needs an API key and its "
                 "real results are imported via import_csv.py."),
    }


@router.post("/run")
def engine_run(req: EngineRunRequest) -> dict:
    """Run the engine. Dry-run = safe preview; live = gated on the API key."""
    global _last_run

    if req.live:
        # Live spends money and would need a key + a background worker + import.
        # Until a key exists it cannot run — fail closed with the runbook hint.
        if not _anthropic_ready():
            raise HTTPException(
                status_code=400,
                detail=("Live run needs ANTHROPIC_API_KEY (and a research key). "
                        "Add it to .env, then: python -m pipeline.runner --top 5 "
                        "--live --max-usd 1  (see .claude/go-live-runbook.md). "
                        "Meanwhile, run a dry-run smoke test from here."),
            )
        # Key present: a real multi-company live run is heavy — defer to the CLI
        # so this request can't hang, and so imports stay explicit/auditable.
        raise HTTPException(
            status_code=501,
            detail=("Live runs are launched from the CLI for now: "
                    "python -m pipeline.runner --top 5 --live --max-usd 1 && "
                    "python import_csv.py data/csv/engine_run.csv"),
        )

    # ── Dry-run: real engine, probe fixture, zero cost, no DB writes ─────────
    from pipeline import runner
    from pipeline.config import EngineConfig

    cfg = EngineConfig.load(live=False)
    try:
        result = runner.run_company(
            cfg, "Probe Diagnostics AG", "Diagnostics", fixture=_FIXTURE)
    except Exception as exc:                     # never 500 the dashboard
        logger.exception("[engine] dry-run failed")
        raise HTTPException(status_code=500, detail=f"Dry-run failed: {exc}")

    _last_run = {
        "mode": "dry-run",
        "company": result.name,
        "assessed_score": result.assessed_score,
        "coverage": result.coverage,
        "outreach_eligible": result.outreach_eligible(cfg.outreach_threshold),
        "signals": [
            {"category": s.signal.category, "total": s.total,
             "confidence": s.signal.confidence}
            for s in result.signals
        ],
        "signals_not_evidenced": result.signals_not_evidenced,
        "intelligence_summary": result.intelligence_summary,
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "cost_usd": 0.0,
        "imported": False,          # dry-run NEVER writes the companies table
    }
    logger.info("[engine] dry-run smoke test: %s scored %.1f",
                result.name, result.assessed_score)
    return _last_run
