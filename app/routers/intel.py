"""Market Intelligence API — backed by the real 492-row TPDL pipeline output.

Reads from the `companies` table (imported via import_csv.py).
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Company

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/intel", tags=["intel"])


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def _signal_block(c: Company, i: int) -> Optional[dict]:
    """Pack Signal N columns into a structured dict, or None if no category."""
    cat = getattr(c, f"s{i}_category")
    if not cat:
        return None
    urls = getattr(c, f"s{i}_urls") or ""
    sources = getattr(c, f"s{i}_sources") or ""
    return {
        "category":       cat,
        "what_happened":  getattr(c, f"s{i}_what_happened"),
        "why_it_matters": getattr(c, f"s{i}_why_it_matters"),
        "tpdl_relevance": getattr(c, f"s{i}_tpdl_relevance"),
        "confidence":     getattr(c, f"s{i}_confidence"),
        "sources":        [s.strip() for s in sources.split(";") if s.strip()],
        "urls":           [u.strip() for u in urls.split(";") if u.strip()],
    }


def _serialize_company(c: Company) -> dict:
    signals = [b for b in (_signal_block(c, i) for i in (1, 2, 3)) if b]
    not_evidenced = [
        s.strip() for s in (c.signals_not_evidenced or "").split(";") if s.strip()
    ]
    return {
        "name":          c.name,
        "sector":        c.sector,
        "sector_bucket": c.sector_bucket,
        "website":       c.website,
        "location":      c.location,
        "revenue":       c.revenue,
        "assessed_score":     c.assessed_score,
        "coverage":           c.coverage,
        "outreach_eligible":  c.outreach_eligible,
        "intelligence_summary": c.intelligence_summary,
        "signals_found":      c.signals_found,
        "signals_not_evidenced": not_evidenced,
        "signals":            signals,
        "tech_stack_summary": c.tech_stack_summary,
        "historical_context": c.historical_context,
        "icp_flag":           c.icp_flag,
        "review_flag":        c.review_flag,
        "review_flag_reason": c.review_flag_reason,
        "run_date":           c.run_date.isoformat() if c.run_date else None,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/companies")
def list_companies(
    sector_bucket: Optional[str] = None,
    signal_type: Optional[str] = None,
    icp_flag: Optional[bool] = None,
    review_flag: Optional[bool] = None,
    outreach_eligible: Optional[bool] = None,
    min_score: Optional[float] = None,
    search: Optional[str] = None,
    limit: int = 1000,
    db: Session = Depends(get_db),
) -> list[dict]:
    q = db.query(Company)

    if sector_bucket:
        q = q.filter(Company.sector_bucket == sector_bucket)
    if icp_flag is not None:
        q = q.filter(Company.icp_flag.is_(icp_flag))
    if review_flag is not None:
        q = q.filter(Company.review_flag.is_(review_flag))
    if outreach_eligible is not None:
        q = q.filter(Company.outreach_eligible.is_(outreach_eligible))
    if min_score is not None:
        q = q.filter(Company.assessed_score >= min_score)
    if signal_type:
        from app.models import Signal
        q = q.filter(Company.name.in_(
            db.query(Signal.company_name).filter(Signal.category == signal_type)
        ))
    if search:
        s = f"%{search.strip()}%"
        q = q.filter(or_(Company.name.ilike(s), Company.website.ilike(s)))

    rows = q.order_by(Company.assessed_score.desc()).limit(min(limit, 2000)).all()
    return [_serialize_company(r) for r in rows]


@router.get("/companies/{name}")
def get_company(name: str, db: Session = Depends(get_db)) -> dict:
    c = db.get(Company, name)
    if c is None:
        raise HTTPException(status_code=404, detail=f"Company '{name}' not found")
    return _serialize_company(c)


@router.get("/stats")
def stats(db: Session = Depends(get_db)) -> dict:
    total       = db.query(func.count(Company.name)).scalar() or 0
    icp_flagged = db.query(func.count(Company.name)).filter(Company.icp_flag.is_(True)).scalar() or 0
    in_scope    = total - icp_flagged
    eligible    = db.query(func.count(Company.name)).filter(Company.outreach_eligible.is_(True)).scalar() or 0
    reviewed    = db.query(func.count(Company.name)).filter(Company.review_flag.is_(True)).scalar() or 0

    # Score bands — CONTIGUOUS so every non-null score lands in exactly one
    # (the old between(5,7.999)/between(1,4.999)/==0 dropped fractional scores in
    # the gaps 0<x<1, 4.999<x<5, 7.999<x<8, so band counts undershot the total).
    bands_raw = db.query(
        func.sum(case((Company.assessed_score >= 8, 1), else_=0)),
        func.sum(case((and_(Company.assessed_score >= 5, Company.assessed_score < 8), 1), else_=0)),
        func.sum(case((and_(Company.assessed_score >= 1, Company.assessed_score < 5), 1), else_=0)),
        func.sum(case((Company.assessed_score < 1, 1), else_=0)),
    ).one()
    score_distribution = [
        {"label": "8+ Eligible", "count": int(bands_raw[0] or 0)},
        {"label": "5–7 Monitor", "count": int(bands_raw[1] or 0)},
        {"label": "1–4 Weak",    "count": int(bands_raw[2] or 0)},
        {"label": "0 No signal", "count": int(bands_raw[3] or 0)},
    ]

    # Signal coverage — one GROUP BY over the normalised signals table
    # (was 6 separate triple-OR queries over the slot columns)
    from app.models import Signal
    signal_types = [
        "leadership_change", "hiring", "ma_expansion",
        "pe_event", "digital_initiative", "org_restructuring",
    ]
    coverage_rows = (
        db.query(Signal.category, func.count(func.distinct(Signal.company_name)))
        .group_by(Signal.category)
        .all()
    )
    coverage_map = {cat: n for cat, n in coverage_rows}
    signal_coverage = [
        {"signal_type": sig, "count": coverage_map.get(sig, 0)}
        for sig in signal_types
    ]

    # Sector distribution by bucket
    sector_rows = (
        db.query(Company.sector_bucket, func.count(Company.name))
        .group_by(Company.sector_bucket)
        .order_by(func.count(Company.name).desc())
        .all()
    )
    sector_distribution = [{"sector": s, "count": n} for s, n in sector_rows]

    # Pick the latest run_date as "last run"
    last_run = db.query(func.max(Company.run_date)).scalar()

    return {
        "pipeline": {
            "total_companies":    total,
            "in_scope":           in_scope,
            "icp_flagged":        icp_flagged,
            "outreach_eligible":  eligible,
            "review_flagged":     reviewed,
            "last_run":           last_run.isoformat() if isinstance(last_run, datetime) else None,
            "pipeline_version":   "v1.1.0",
        },
        "score_distribution":   score_distribution,
        "signal_coverage":      signal_coverage,
        "sector_distribution":  sector_distribution,
    }


@router.get("/signals")
def list_signals(limit: int = 50, db: Session = Depends(get_db)) -> list[dict]:
    """Flat signal timeline across the full company set, highest score first."""
    from app.models import Signal
    rows = (
        db.query(Signal, Company)
        .join(Company, Signal.company_name == Company.name)
        .filter(Company.assessed_score > 0)
        .order_by(Company.assessed_score.desc(), Signal.slot.asc())
        .limit(limit)
        .all()
    )
    return [
        {
            "company":        c.name,
            "sector_bucket":  c.sector_bucket,
            "location":       c.location,
            "score":          c.assessed_score,
            "category":       s.category,
            "confidence":     s.confidence,
            "what_happened":  s.what_happened,
            "tpdl_relevance": s.tpdl_relevance,
        }
        for s, c in rows
    ]
