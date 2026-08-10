"""Usage & credits API — one card per subscription.

GET /api/credits → provider panels (SerpAPI/Apify/Firecrawl live account
endpoints — free, no credit consumed; Anthropic = local token tally;
Exa/Perplexity/Apollo = configured-state cards).

Network panels run concurrently in worker threads so one slow provider
never blocks the page.
"""
import asyncio

from fastapi import APIRouter, Depends
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Company
from app.tools import usage

router = APIRouter(prefix="/api/credits", tags=["credits"])


@router.get("")
async def credits(db: Session = Depends(get_db)) -> dict:
    panels = await asyncio.to_thread(usage.all_panels, db)
    configured = [p for p in panels if p["configured"]]
    return {
        "panels": panels,
        "summary": {
            "configured": len(configured),
            "total": len(panels),
            "errors": sum(1 for p in configured if not p["ok"]),
        },
    }


@router.get("/runs")
def engine_runs(db: Session = Depends(get_db)) -> dict:
    """Engine/import run history — one row per import_run_id.

    This is what unblocks Maya's /summary movement narrative: multiple runs
    today, the counter increments as the rebuilt engine produces new runs.
    """
    rows = (
        db.query(
            Company.import_run_id,
            func.count(Company.name).label("companies"),
            func.sum(case((Company.outreach_eligible.is_(True), 1), else_=0))
            .label("eligible"),
            func.max(Company.run_date).label("run_date"),
            func.max(Company.imported_at).label("imported_at"),
        )
        .group_by(Company.import_run_id)
        .order_by(func.max(Company.imported_at).desc())
        .all()
    )
    return {
        "runs": [
            {
                "run_id": r.import_run_id or "—",
                "companies": r.companies,
                "eligible": int(r.eligible or 0),
                "run_date": r.run_date.isoformat() if r.run_date else None,
                "imported_at": r.imported_at.isoformat() if r.imported_at else None,
            }
            for r in rows
        ],
    }
