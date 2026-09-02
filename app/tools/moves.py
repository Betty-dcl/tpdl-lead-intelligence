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


def mark_connected(db, move_id: int):
    """A human confirms they actually sent the LinkedIn connection request
    (always 100% manual — never triggered by this function itself). Returns
    (move, outcome) — outcome in {"ok", "not_approved", "not_found"}. Sets
    connection_sent_at=now and computes follow_up_date (~4 months out,
    exec_titles.compute_follow_up_date — Nathalie's rationale: people start
    making strategic changes ~6 months into a new role, so following up just
    BEFORE that window is the useful moment)."""
    from app.models import ExecutiveMove
    from app.tools.exec_titles import compute_follow_up_date

    m = db.get(ExecutiveMove, move_id)
    if m is None:
        return None, "not_found"
    if m.status != "approved":
        return m, "not_approved"
    now = datetime.now(timezone.utc)
    m.status = "connection_sent"
    m.connection_sent_at = now
    m.follow_up_date = compute_follow_up_date(now.date())
    db.commit()
    return m, "ok"


def due_for_follow_up(db, today=None):
    """Moves whose 4-month follow-up window has arrived. A plain query, not a
    scheduler — a human runs `/moves followup` whenever they check in
    (weekly), same pull-based idiom as every other command in this app."""
    from app.models import ExecutiveMove

    today = today or datetime.now(timezone.utc).date()
    return (
        db.query(ExecutiveMove)
        .filter(ExecutiveMove.status == "connection_sent")
        .filter(ExecutiveMove.follow_up_date.isnot(None))
        .filter(ExecutiveMove.follow_up_date <= today)
        .order_by(ExecutiveMove.follow_up_date)
        .all()
    )


def mark_followed_up(db, move_id: int):
    """Returns (move, outcome) — outcome in {"ok", "not_due", "not_found"}."""
    from app.models import ExecutiveMove

    m = db.get(ExecutiveMove, move_id)
    if m is None:
        return None, "not_found"
    if m.status != "connection_sent":
        return m, "not_due"
    m.status = "follow_up_sent"
    m.follow_up_sent_at = datetime.now(timezone.utc)
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
        "connection_sent_at": m.connection_sent_at.isoformat() if m.connection_sent_at else None,
        "follow_up_date": m.follow_up_date.isoformat() if m.follow_up_date else None,
        "follow_up_sent_at": m.follow_up_sent_at.isoformat() if m.follow_up_sent_at else None,
    }
