"""Human review queue (Vera) — the API behind the /review page.

GET  /api/review            → flagged companies + their signals + review status
POST /api/review/{name}     → record a human decision (approved | rejected + note)

A review-flagged company needs a ~60-second human check before TPDL acts on the
signal. Approving means "safe to act"; rejecting means "don't use this signal".
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Company, Signal

router = APIRouter(prefix="/api/review", tags=["review"])


class Decision(BaseModel):
    decision: str            # "approved" | "rejected"
    note: str | None = None


# ---------------------------------------------------------------------------
# Urgency tiering — a flat "flagged = flagged" list buries the flags that
# actually need a human first. Not all reasons carry the same real risk:
#   1. the underlying EVENT may not be real (entirely speculative/hedged) —
#      verify before trusting the signal at all.
#   2. the event is likely real but partially unverified (undated, or one of
#      several quotes hedged) — verify soon, lower risk than tier 1.
#   3. cosmetic / internal QA nit (extraction wording rules, summary length)
#      — the business signal itself is probably fine.
# Matched by substring on `review_flag_reason` (written by app/tools/integrity.py
# and the pipeline's QA checks) — no new column, purely a display/ordering layer.
# ---------------------------------------------------------------------------

def _urgency(reason: str | None) -> tuple[int, str]:
    r = (reason or "").lower()
    if "resting entirely on" in r:
        return (1, "Verify first — the event itself may not be real")
    if "no approximate date" in r or "speculative/negated quote" in r:
        return (2, "Verify soon — likely real, partially unverified")
    if not reason:
        return (3, "Low priority — no reason on file")
    return (3, "Low priority — formatting/QA nit, signal likely sound")


@router.get("")
def list_review(status: str = "pending", db: Session = Depends(get_db)) -> dict:
    """status: pending (default) | reviewed | all."""
    q = db.query(Company).filter(Company.review_flag.is_(True))
    if status == "pending":
        q = q.filter(Company.review_status.is_(None))
    elif status == "reviewed":
        q = q.filter(Company.review_status.isnot(None))
    companies = q.all()

    items = []
    for c in companies:
        signals = db.query(Signal).filter(Signal.company_name == c.name).all()
        tier, label = _urgency(c.review_flag_reason)
        items.append({
            "name": c.name,
            "sector": c.sector_bucket,
            "score": c.assessed_score,
            "coverage": c.coverage,
            "reason": c.review_flag_reason,
            "urgency_tier": tier,
            "urgency_label": label,
            "review_status": c.review_status,
            "reviewed_at": c.reviewed_at.isoformat() if c.reviewed_at else None,
            "reviewed_note": c.reviewed_note,
            "signals": [
                {
                    "category": s.category,
                    "what_happened": s.what_happened,
                    "confidence": s.confidence,
                    "sources": s.sources,
                    "urls": s.urls,
                }
                for s in signals
            ],
        })

    # Real urgency first, highest score as the tiebreaker within a tier —
    # not a flat score sort, which is what buried the actually-risky flags.
    items.sort(key=lambda it: (it["urgency_tier"], -it["score"]))

    flagged = db.query(func.count(Company.name)).filter(Company.review_flag.is_(True)).scalar() or 0
    pending = (db.query(func.count(Company.name))
               .filter(Company.review_flag.is_(True), Company.review_status.is_(None))
               .scalar() or 0)
    by_tier = {1: 0, 2: 0, 3: 0}
    for it in items:
        by_tier[it["urgency_tier"]] += 1
    return {"items": items, "summary": {"flagged": flagged, "pending": pending,
                                        "reviewed": flagged - pending, "by_urgency": by_tier}}


@router.post("/{name}")
def record_decision(name: str, body: Decision, db: Session = Depends(get_db)) -> dict:
    if body.decision not in ("approved", "rejected"):
        raise HTTPException(status_code=422, detail="decision must be 'approved' or 'rejected'")
    c = db.get(Company, name)
    if c is None:
        raise HTTPException(status_code=404, detail=f"company not found: {name}")
    c.review_status = body.decision
    c.reviewed_at = datetime.now(timezone.utc)
    c.reviewed_note = (body.note or "").strip() or None
    db.commit()
    return {"name": c.name, "review_status": c.review_status,
            "reviewed_at": c.reviewed_at.isoformat()}
