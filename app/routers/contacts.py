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
from app.tools.scraper_brief import (
    CAPTURE_FIELDS,
    ICP_FUNCTION_TITLES,
    MED_AFFAIRS_TITLES,
    SALESNAV_KEYWORDS,
    SENIORITY_FLOOR_LABEL,
    company_brief,
)
from app.tools.shortlist import shortlist_bands

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


# ---------------------------------------------------------------------------
# Scraper-ready brief export — the deliverable Inès already builds in chat
# (app/tools/scraper_brief.py), but as a downloadable file so it can be
# handed straight to Marketeering.ai / a human SDR without depending on
# Apollo or Kaspr — the actual sourcing is done by the agency, not an API.
# Pure DB read + deterministic formatting, no network, no LLM call.
# ---------------------------------------------------------------------------

_BRIEF_HEADER = [
    "Company", "Sector", "Location", "Score", "Lead signal", "Priority roles",
    "Radar country", "Lunch campaign", "Default language", "Sales Nav geography",
    "Seniority floor", "Sales Nav keywords", "Tie-back checklist", "Capture per contact",
]


def _brief_row(c: Company) -> list[str]:
    b = company_brief(c)
    r = b["radar"]
    return [
        b["company"], b["sector"], b["location"], f"{b['score']:.1f}" if b["score"] is not None else "",
        b["lead_signal"], "; ".join(b["priority_roles"]),
        r["country"] or "other", "yes" if r["lunch_campaign"] else "no", r["language"],
        b["salesnav_geography"], SENIORITY_FLOOR_LABEL, " OR ".join(SALESNAV_KEYWORDS),
        " | ".join(b["tieback"]), "; ".join(CAPTURE_FIELDS),
    ]


@router.get("/scraper_brief.csv")
def export_scraper_brief_csv(db: Session = Depends(get_db)):
    """One row per ACT NOW company (score ≥ 8, in-scope) — the scraper-ready
    targeting brief, ready to hand to the sourcing agency today. A short legend
    of the 4 shared ICP functions + the separate Medical Affairs sub-batch is
    written above the table (identical for every company, so not repeated
    620 times per row)."""
    import csv
    import io

    from fastapi.responses import Response

    act, _monitor = shortlist_bands(db)

    buf = io.StringIO()
    buf.write("sep=;\r\n")
    buf.write(
        "TPDL scraper-ready brief — ACT NOW shortlist (score >= 8, in-scope)\r\n"
        "Shared ICP functions to layer over the per-company lead signal below:\r\n"
    )
    for fam, titles in ICP_FUNCTION_TITLES.items():
        buf.write(f"  {fam}: {'; '.join(titles)}\r\n")
    buf.write(
        f"  Medical Affairs (SEPARATE sub-batch for Nathalie, do not mix in): "
        f"{'; '.join(MED_AFFAIRS_TITLES)}\r\n"
        "No invented people — names are the scraper/agency's job.\r\n\r\n"
    )

    w = csv.writer(buf, delimiter=";", lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
    w.writerow(_BRIEF_HEADER)
    for c in act:
        w.writerow(_brief_row(c))

    content = "﻿" + buf.getvalue()
    return Response(
        content=content, media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="tpdl_scraper_brief.csv"'},
    )
