"""Engine → dashboard usage bridge.

Every live Anthropic call the engine makes (Sonnet 5 extraction, Opus 4.8
interpretation) is logged into the dashboard's `activity_log` so the Usage
page's LOCAL tally reflects engine runs, not just chat. Rows are logged under
agent `hugo` (the engine's operator persona) with the real per-call model, so
the per-model pricing in `app/tools/usage.py` costs them correctly.

FAIL-OPEN by design: the engine must run standalone — if the dashboard DB is
unavailable or the insert fails, the run continues and nothing is lost but a
tally row.
"""
from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)

ENGINE_AGENT_ID = "hugo"   # activity_log.agent_id is an FK to agents.id


def log_anthropic_call(model: str, usage, company: str, stage: str) -> None:
    """Record one live Anthropic call (tokens + model) in the dashboard tally.

    `usage` is the SDK response.usage object (input_tokens/output_tokens).
    """
    try:
        from app.database import SessionLocal
        from app.models import ActivityLog

        with SessionLocal() as db:
            db.add(ActivityLog(
                agent_id=ENGINE_AGENT_ID,
                action="engine_call",
                activity_metadata=json.dumps({
                    "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
                    "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
                    "model": model,
                    "company": company,
                    "stage": stage,
                }),
            ))
            db.commit()
    except Exception as exc:   # noqa: BLE001 — never let the tally kill a paid run
        logger.debug("[usage_log] skipped (%s)", exc)
