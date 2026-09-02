"""Executive-move state transitions + serialization — SHARED by Inès's
`/moves` chat command (app/agents/ines.py) and the REST API (dashboard UI,
app/routers/intel.py), so the two can never disagree about what "approve" or
"dismiss" means. Same "single shared definition" convention as
app/tools/shortlist.py (Maya/Inès)."""
from __future__ import annotations

from datetime import datetime, timezone


def approve_move(db, move_id: int):
    """Returns (move, outcome) — outcome in {"ok", "already", "not_found"}."""
    from app.models import ExecutiveMove

    m = db.get(ExecutiveMove, move_id)
    if m is None:
        return None, "not_found"
    if m.status != "new":
        return m, "already"
    m.status = "approved"
    db.commit()
    return m, "ok"


def dismiss_move(db, move_id: int):
    """Returns (move, outcome) — outcome in {"ok", "not_found"}. Sets
    dismissed_at (the GDPR retention clock, RETENTION_DAYS_DISMISSED days)."""
    from app.models import ExecutiveMove

    m = db.get(ExecutiveMove, move_id)
    if m is None:
        return None, "not_found"
    m.status = "dismissed"
    m.dismissed_at = datetime.now(timezone.utc)
    db.commit()
    return m, "ok"


def serialize_move(m) -> dict:
    """One ExecutiveMove row → the dashboard-ready dict (contact-card shape)."""
    from app.tools.icp import market_tier

    return {
        "id": m.id,
        "person_name": m.person_name,
        "new_title": m.new_title,
        "new_company": m.new_company,
        "previous_company": m.previous_company,
        "previous_title": m.previous_title,
        "move_date": m.move_date.isoformat() if m.move_date else None,
        "location": m.location,
        "market_tier": market_tier(m.location),
        "seniority_tier": m.seniority_tier,
        "role_function": m.role_function,
        "quote": m.quote,
        "source_url": m.source_url,
        "source_type": m.source_type,
        "status": m.status,
        "resolved_company_name": m.resolved_company_name,
        "discovered_at": m.discovered_at.isoformat() if m.discovered_at else None,
    }
