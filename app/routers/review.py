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


@router.get("")
def list_review(status: str = "pending", db: Session = Depends(get_db)) -> dict:
    """status: pending (default) | reviewed | all."""
    q = db.query(Company).filter(Company.review_flag.is_(True))
    if status == "pending":
        q = q.filter(Company.review_status.is_(None))
    elif status == "reviewed":
        q = q.filter(Company.review_status.isnot(None))
    companies = q.order_by(Company.assessed_score.desc()).all()

    items = []
    for c in companies:
        signals = db.query(Signal).filter(Signal.company_name == c.name).all()
        items.append({
            "name": c.name,
            "sector": c.sector_bucket,
            "score": c.assessed_score,
            "coverage": c.coverage,
            "reason": c.review_flag_reason,
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

    flagged = db.query(func.count(Company.name)).filter(Company.review_flag.is_(True)).scalar() or 0
    pending = (db.query(func.count(Company.name))
               .filter(Company.review_flag.is_(True), Company.review_status.is_(None))
               .scalar() or 0)
    return {"items": items, "summary": {"flagged": flagged, "pending": pending,
                                        "reviewed": flagged - pending}}


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
