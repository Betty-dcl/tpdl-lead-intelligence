"""Contacts / CRM API — Inès's territory.

Two sources:
  - /api/contacts/radars : Lunch Campaign candidates computed live from the
    scored companies' locations (Switzerland / Spain). Works today on real data,
    before Apollo is connected.
  - /api/contacts        : decision-maker contacts stored by Inès (via Apollo),
    with their radar tags. Empty until Apollo is wired.
"""
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Company, Contact, RunSnapshot
from app.routers.intel import NEOTEK_REFERENCE_RUN, _neotek_baseline
from app.tools.radars import detect_country

router = APIRouter(prefix="/api/contacts", tags=["contacts"])


@router.get("/radars")
def radar_candidates(db: Session = Depends(get_db)) -> dict:
    """Company-level Lunch Campaign candidates (CH / Spain), highest score first.
    Each entry carries its run date + movement vs the Neotek May run, so the
    Contacts radar reads the SAME freshly-scored companies the Sales page shows."""
    rows = (
        db.query(Company)
        .filter(Company.icp_flag.is_(False))
        .filter(Company.location.isnot(None))
        .all()
    )
    baseline = _neotek_baseline(db)
    last_run = db.query(func.max(Company.run_date)).scalar()
    latest_day = last_run.date().isoformat() if isinstance(last_run, datetime) else None

    ch: list[dict] = []
    es: list[dict] = []
    for c in rows:
        country = detect_country(c.location)
        if country not in ("CH", "ES"):
            continue
        run_day = c.run_date.date().isoformat() if c.run_date else None
        neo = baseline.get(c.name)
        entry = {
            "company": c.name,
            "sector": c.sector_bucket or "—",
            "location": c.location or "—",
            "score": c.assessed_score,
            "outreach_eligible": bool(c.outreach_eligible),
            "run_date": run_day,
            "fresh": run_day == latest_day,
            "neotek_score": neo,
            "delta": round((c.assessed_score or 0) - neo, 1) if neo is not None else None,
            "reappeared": neo is not None,
        }
        (ch if country == "CH" else es).append(entry)
    ch.sort(key=lambda e: e["score"] or 0, reverse=True)
    es.sort(key=lambda e: e["score"] or 0, reverse=True)
    fresh = sum(1 for e in ch + es if e["fresh"])
    eligible = sum(1 for e in ch + es if e["outreach_eligible"])
    return {"switzerland": ch, "spain": es,
            "counts": {"switzerland": len(ch), "spain": len(es),
                       "fresh": fresh, "eligible": eligible},
            "latest_run": latest_day}


@router.get("")
def list_contacts(db: Session = Depends(get_db)) -> dict:
    """Decision-maker contacts stored by Inès (via Apollo) with radar tags."""
    rows = db.query(Contact).order_by(Contact.id.desc()).all()
    contacts = [
        {
            "id": r.id,
            "full_name": r.full_name,
            "title": r.title,
            "company": r.company_name,
            "location": r.location,
            "country": r.country,
            "language": r.language,
            "lunch_campaign": bool(r.lunch_campaign),
            "premium": bool(r.premium),
            "status": r.status,
            "linkedin_url": r.linkedin_url,
        }
        for r in rows
    ]
    return {"contacts": contacts, "apollo_connected": bool(settings.apollo_api_key)}
