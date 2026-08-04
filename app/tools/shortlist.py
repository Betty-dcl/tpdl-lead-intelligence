"""Shared shortlist definition — Maya OWNS it, Inès CONSUMES it.

The score-banded shortlist is defined ONCE here so Maya's `/shortlist` and Inès's
batch hand-off (`/contacts shortlist`) can never disagree on what "the shortlist"
is. Pure DB read + deterministic banding + tiebreakers, no network.

Bands (constitution threshold = 8):
  ACT NOW  — in-scope, assessed_score >= 8 (outreach-eligible)
  MONITOR  — in-scope, 5 <= score < 8 (next-run bench, not outreach yet)
Both sorted by score, then coverage depth, then freshness (latest run first).
"""
from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Company

ACT_NOW_FLOOR = 8.0
MONITOR_FLOOR = 5.0


def _coverage_depth(c: Company) -> int:
    cov = c.coverage or ""
    return int(cov[0]) if cov[:1].isdigit() else 0


def shortlist_bands(db: Session) -> tuple[list[Company], list[Company]]:
    """Return (act_now, monitor) — in-scope companies banded by score."""
    rows = (db.query(Company)
            .filter(Company.icp_flag.is_(False))
            .order_by(Company.assessed_score.desc()).all())
    latest = db.query(func.max(Company.run_date)).scalar()
    latest_day = latest.date() if latest else None

    def _sig(c: Company):
        fresh = 1 if (c.run_date and latest_day and c.run_date.date() == latest_day) else 0
        return (c.assessed_score, _coverage_depth(c), fresh)

    act = sorted([c for c in rows if c.assessed_score >= ACT_NOW_FLOOR],
                 key=_sig, reverse=True)
    monitor = sorted([c for c in rows if MONITOR_FLOOR <= c.assessed_score < ACT_NOW_FLOOR],
                     key=_sig, reverse=True)
    return act, monitor
