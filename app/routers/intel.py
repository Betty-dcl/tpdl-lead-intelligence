"""Market Intelligence API — backed by the real 492-row TPDL pipeline output.

Reads from the `companies` table (imported via import_csv.py).
"""
import logging
import re
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Company, RunSnapshot
from app.tools.icp import market_tier
from app.tools.radars import geo_region

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/intel", tags=["intel"])

# The 25/05 run is the ORIGINAL Neotek engine (external reference). Every company
# in our own July run was also in that Neotek run, so we can show each company's
# movement since Neotek. NB: the two runs come from DIFFERENT engines (Neotek in
# May, TPDL's rebuilt engine in July), so a delta mixes a real change in signal
# with an engine change — the UI is explicit about that caveat.
NEOTEK_REFERENCE_RUN = "cb97cf5d50d2"
NEOTEK_REFERENCE_DATE = "2026-05-25"   # the day the Neotek reference run is dated


# ---------------------------------------------------------------------------
# Neotek baseline (May reference) — company_name → score
# ---------------------------------------------------------------------------

def _neotek_baseline(db: Session) -> dict[str, float]:
    rows = (
        db.query(RunSnapshot.company_name, RunSnapshot.assessed_score)
        .filter(RunSnapshot.import_run_id == NEOTEK_REFERENCE_RUN)
        .all()
    )
    return {name: (score or 0.0) for name, score in rows}


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def _corroboration(urls: list[str], sources: list[str]) -> dict:
    """Recompute the corroboration sub-score exactly as the scoring engine does,
    so the UI can SHOW where the score comes from (not invent it):
      2+ distinct source URLs → 2 · 1 verified URL → 1 · no URL (e.g. Perplexity
      only) → 0. This is a faithful re-derivation from the stored evidence."""
    n_urls = len(urls)
    if n_urls >= 2:
        pts, note = 2, "2+ independent sources"
    elif n_urls == 1:
        pts, note = 1, "1 verified URL"
    else:
        pts, note = 0, "no verifiable URL (uncorroborated)"
    return {"points": pts, "max": 2, "note": note, "url_count": n_urls}


def _signal_block(c: Company, i: int) -> Optional[dict]:
    """Pack Signal N columns into a structured dict, or None if no category."""
    cat = getattr(c, f"s{i}_category")
    if not cat:
        return None
    urls = getattr(c, f"s{i}_urls") or ""
    sources = getattr(c, f"s{i}_sources") or ""
    url_list = [u.strip() for u in urls.split(";") if u.strip()]
    src_list = [s.strip() for s in sources.split(";") if s.strip()]
    return {
        "category":       cat,
        "what_happened":  getattr(c, f"s{i}_what_happened"),
        "why_it_matters": getattr(c, f"s{i}_why_it_matters"),
        "tpdl_relevance": getattr(c, f"s{i}_tpdl_relevance"),
        "confidence":     getattr(c, f"s{i}_confidence"),
        "sources":        src_list,
        "urls":           url_list,
        "corroboration":  _corroboration(url_list, src_list),
    }


def _workspace_map(db: Session, names: list[str]) -> dict[str, dict]:
    """Bulk claim + status lookup for a list of company names — one query each,
    not N+1, so listing hundreds of companies stays cheap. Sparse by design:
    most companies have no row (unclaimed, status 'new') until a human acts."""
    from app.models import CompanyAssignment, CompanyStatus, User

    if not names:
        return {}
    out: dict[str, dict] = {}
    statuses = (db.query(CompanyStatus)
                .filter(CompanyStatus.company_name.in_(names)).all())
    for s in statuses:
        out.setdefault(s.company_name, {})["status"] = s.status
    assigns = (db.query(CompanyAssignment, User)
               .join(User, User.id == CompanyAssignment.user_id)
               .filter(CompanyAssignment.company_name.in_(names)).all())
    for a, u in assigns:
        out.setdefault(a.company_name, {})["assigned_to"] = u.display_name
    return out


def _serialize_company(
    c: Company,
    baseline: Optional[dict[str, float]] = None,
    workspace_map: Optional[dict[str, dict]] = None,
) -> dict:
    signals = [b for b in (_signal_block(c, i) for i in (1, 2, 3)) if b]
    not_evidenced = [
        s.strip() for s in (c.signals_not_evidenced or "").split(";") if s.strip()
    ]
    # Movement since the Neotek May reference run. A "delta vs Neotek" only
    # means something for a company RE-SCORED after May. Rows still dated on the
    # Neotek run day ARE the Neotek data, so comparing them to themselves would
    # print a meaningless "±0" — instead we mark them as un-refreshed (vintage
    # "neotek_may") and report no delta. Only refreshed rows carry a real delta.
    day = c.run_date.date().isoformat() if c.run_date else None
    refreshed = day is not None and day != NEOTEK_REFERENCE_DATE
    vintage = "refreshed" if refreshed else "neotek_may"
    neotek = None
    delta = None
    reappeared = False
    if baseline is not None and c.name in baseline:
        neotek = baseline[c.name]
        if refreshed:
            delta = round((c.assessed_score or 0.0) - neotek, 1)
            reappeared = True
    ws = (workspace_map or {}).get(c.name) or {}
    return {
        "name":          c.name,
        "sector":        c.sector,
        "sector_bucket": c.sector_bucket,
        "website":       c.website,
        "location":      c.location,
        "geo_region":    geo_region(c.location),
        "market_tier":   market_tier(c.location),   # core (CH/ES/ME/Europe) | world
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
        "icp_flag_reason":    c.icp_flag_reason,
        "review_flag":        c.review_flag,
        "review_flag_reason": c.review_flag_reason,
        "run_date":           c.run_date.isoformat() if c.run_date else None,
        "run_label":          _date_label(day),   # exact scan date: "May 25" / "Jul 17" / "Jul 23"
        # Neotek → now movement
        "neotek_score":       neotek,
        "delta":              delta,
        "reappeared":         reappeared,
        "vintage":            vintage,   # "refreshed" (re-scored) | "neotek_may"
        # Team workspace — who's on it, what stage it's at. Absent (None) means
        # "unclaimed / no status set yet", not an error.
        "assigned_to":        ws.get("assigned_to"),
        "workspace_status":   ws.get("status"),
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
    baseline = _neotek_baseline(db)
    workspace_map = _workspace_map(db, [r.name for r in rows])
    return [_serialize_company(r, baseline, workspace_map) for r in rows]


@router.get("/companies/{name}")
def get_company(name: str, db: Session = Depends(get_db)) -> dict:
    c = db.get(Company, name)
    if c is None:
        raise HTTPException(status_code=404, detail=f"Company '{name}' not found")
    return _serialize_company(c, _neotek_baseline(db))


@router.get("/pipeline")
def sales_pipeline(company: Optional[str] = None, db: Session = Depends(get_db)) -> dict:
    """Live view of the Sales chain on ONE company: Hugo → Maya → Inès → Julie.

    Every stage shows its REAL contribution assembled deterministically from the
    scored row — no LLM call, no invention. The picker lists Maya's ACT NOW band;
    the default is its top company. This is the wiring made visible: each stage
    consumes the previous stage's output exactly as the agents do in chat.
    """
    from app.models import Contact
    from app.tools import apollo, sectors
    from app.tools.radars import apply_radars
    from app.tools.shortlist import shortlist_bands

    act, monitor = shortlist_bands(db)
    picker = [{"name": c.name, "score": c.assessed_score} for c in act[:30]]

    target = None
    if company:
        target = db.get(Company, company)
        if target is None:
            low = company.strip().lower()
            target = next((c for c in db.query(Company).all()
                           if c.name.lower() == low or low in c.name.lower()), None)
    if target is None:
        target = act[0] if act else (monitor[0] if monitor else None)
    if target is None:
        return {"empty": True, "picker": picker}

    ser = _serialize_company(target, _neotek_baseline(db))

    # Maya: score band + rank among in-scope companies
    in_scope = [s or 0.0 for (s,) in db.query(Company.assessed_score)
                .filter(Company.icp_flag.is_(False)).all()]
    score = target.assessed_score or 0.0
    rank = sum(1 for s in in_scope if s > score) + 1
    band = "ACT NOW" if score >= 8 else ("MONITOR" if score >= 5 else "PARKED")

    # Inès: signal-driven roles + radar + tie-back checks
    lead_signal = target.s1_category
    radar = apply_radars(None, target.location)
    n_contacts = db.query(Contact).filter(Contact.company_name == target.name).count()

    # Julie: sector angle + a hook drawn from the strongest real signal
    angle = sectors.get_sector_angle(target.sector_bucket)
    strongest = ser["signals"][0] if ser["signals"] else None
    hook = (f"{strongest['category']}: {(strongest['what_happened'] or '')[:150]}"
            if strongest else None)

    return {
        "empty": False,
        "picker": picker,
        "company": target.name,
        "sector": target.sector_bucket or "—",
        "location": target.location,
        "icp_flag": target.icp_flag,
        "hugo": {
            "score": ser["assessed_score"], "coverage": ser["coverage"],
            "eligible": ser["outreach_eligible"], "review_flag": ser["review_flag"],
            "summary": ser["intelligence_summary"], "signals": ser["signals"],
        },
        "maya": {
            "band": band, "rank": rank, "total_in_scope": len(in_scope),
            "delta": ser["delta"], "neotek_score": ser["neotek_score"],
            "vintage": ser["vintage"], "run_label": ser["run_label"],
        },
        "ines": {
            "lead_signal": lead_signal or "none evidenced",
            "target_roles": list(apollo.titles_for_signal(lead_signal)),
            "radar": radar,
            "tieback": [
                "Partner (Andrés / Pierre) already connected?",
                "Already in PipeDrive?",
                "1st-degree LinkedIn connection?",
            ],
            "med_affairs_subbatch": True,
            "contacts_stored": n_contacts,
            "engine_connected": apollo.is_configured(),
        },
        "julie": {
            "angle": angle["angle"],
            "angle_defined": sectors.is_defined(target.sector_bucket),
            "proof_points": angle.get("proof_points", []),
            "signal_hook": hook,
            "contact_ready": n_contacts > 0,
        },
    }


@router.get("/companies/{name}/trajectory")
def company_trajectory(name: str, db: Session = Depends(get_db)) -> dict:
    """Score history for one company, oldest → newest, for the evolution curve.
    Point 1 = Neotek May reference; point 2 = the current (July) TPDL-engine run.
    Each point is labelled with the engine that produced it, so the curve is
    honest that it spans an engine change, not just a change in the company."""
    c = db.get(Company, name)
    if c is None:
        raise HTTPException(status_code=404, detail=f"Company '{name}' not found")

    points: list[dict] = []
    # Neotek May baseline (if the company was in it)
    neo = (
        db.query(RunSnapshot)
        .filter(RunSnapshot.import_run_id == NEOTEK_REFERENCE_RUN,
                RunSnapshot.company_name == name)
        .first()
    )
    if neo is not None:
        points.append({
            "run_date": neo.run_date.date().isoformat() if neo.run_date else None,
            "score": neo.assessed_score or 0.0,
            "coverage": neo.coverage,
            "signals_found": neo.signals_found,
            "engine": "Neotek (reference)",
            "current": False,
        })
    # Current TPDL-engine run (the company row itself)
    points.append({
        "run_date": c.run_date.date().isoformat() if c.run_date else None,
        "score": c.assessed_score or 0.0,
        "coverage": c.coverage,
        "signals_found": c.signals_found,
        "engine": "TPDL engine",
        "current": True,
    })
    delta = None
    if neo is not None:
        delta = round((c.assessed_score or 0.0) - (neo.assessed_score or 0.0), 1)
    return {"company": name, "points": points, "delta": delta,
            "reappeared": neo is not None}


@router.get("/companies/{name}/brief.pdf")
def company_brief_pdf(name: str, db: Session = Depends(get_db)):
    """A branded one-page PDF for a single company — the same content as its
    detail page (score + formula, evolution curve, signal cards with sources,
    tech stack, flags), in a form you can send. The per-company CSV would be a
    single row already present in the run export, so we offer the designed PDF."""
    from fastapi.responses import Response
    from app.tools.company_pdf import generate_company_brief_pdf

    c = db.get(Company, name)
    if c is None:
        raise HTTPException(status_code=404, detail=f"Company '{name}' not found")
    company = _serialize_company(c, _neotek_baseline(db))

    # Evolution points: every scan of this company (run_snapshots), deduped to the
    # latest score per run date, oldest → newest — the same curve as Recurring.
    snaps = (
        db.query(RunSnapshot)
        .filter(RunSnapshot.company_name == name)
        .order_by(RunSnapshot.run_date.asc())
        .all()
    )
    by_day: dict[str, float] = {}
    for s in snaps:
        day = s.run_date.date().isoformat() if s.run_date else None
        if day:
            by_day[day] = s.assessed_score or 0.0
    # make sure the company's own current run is represented
    cur_day = c.run_date.date().isoformat() if c.run_date else None
    if cur_day:
        by_day[cur_day] = c.assessed_score or 0.0
    points = [(_date_label(day), score) for day, score in sorted(by_day.items())]

    pdf = generate_company_brief_pdf(company, points)
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_") or "company"
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="tpdl_{safe}_brief.pdf"'})


class ViewPdfPayload(BaseModel):
    title: str = "TPDL view"
    subtitle: str = ""
    columns: list[str]
    rows: list[list]
    widths: Optional[list[float]] = None
    filename: str = "tpdl_view.pdf"


@router.post("/view.pdf")
def view_pdf(payload: ViewPdfPayload):
    """Designed snapshot of a table view (Recurring / Sales). The client posts the
    columns + rows exactly as shown (filters applied, in sort order); we render a
    branded landscape PDF. WYSIWYG — the server does no filtering of its own."""
    from fastapi.responses import Response
    from app.tools.view_pdf import generate_view_pdf

    cols = payload.columns[:16]                     # guard against absurd widths
    rows = [r[:16] for r in payload.rows[:2000]]    # and runaway payloads
    pdf = generate_view_pdf(payload.title, payload.subtitle, cols, rows, payload.widths)
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", payload.filename).strip("_") or "tpdl_view.pdf"
    if not safe.endswith(".pdf"):
        safe += ".pdf"
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{safe}"'})


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


# ---------------------------------------------------------------------------
# Latest-run summary (the "run cockpit" header) + Neotek movement
# ---------------------------------------------------------------------------

def _prior_scores(db: Session, before_day: str) -> dict[str, float]:
    """Each company's most recent score from ANY run before `before_day` (iso).
    This is the 'what we already had in the DB' baseline — broader than the Neotek
    reference, so the Sales cockpit can frame a run against our whole history."""
    best_day: dict[str, str] = {}
    scores: dict[str, float] = {}
    for r in db.query(RunSnapshot).all():
        if not r.run_date:
            continue
        d = r.run_date.date().isoformat()
        if d >= before_day:
            continue
        if r.company_name not in best_day or d > best_day[r.company_name]:
            best_day[r.company_name] = d
            scores[r.company_name] = r.assessed_score or 0.0
    return scores


@router.get("/run")
def latest_run(db: Session = Depends(get_db)) -> dict:
    """Everything the Sales page needs to frame the LATEST run: its date, size,
    band counts, top scorer, and how the run moved vs the Neotek May reference."""
    last_run = db.query(func.max(Company.run_date)).scalar()
    if not isinstance(last_run, datetime):
        return {"has_run": False}
    day = last_run.date()

    rows = (
        db.query(Company)
        .filter(func.date(Company.run_date) == day.isoformat())
        .order_by(Company.assessed_score.desc())
        .all()
    )
    neotek = _neotek_baseline(db)                       # vs the original Neotek May run
    prior = _prior_scores(db, day.isoformat())          # vs each company's previous score in OUR DB

    def band(s: float) -> str:
        s = s or 0
        if s >= 8: return "act_now"
        if s >= 5: return "monitor"
        if s >= 1: return "weak"
        return "none"

    def movement(baseline: dict[str, float]) -> dict:
        reappeared = risers = faders = stable = 0
        top_riser = top_fader = None
        for c in rows:
            if c.name in baseline:
                reappeared += 1
                d = round((c.assessed_score or 0) - baseline[c.name], 1)
                if d > 0:
                    risers += 1
                    if top_riser is None or d > top_riser[1]:
                        top_riser = (c.name, d)
                elif d < 0:
                    faders += 1
                    if top_fader is None or d < top_fader[1]:
                        top_fader = (c.name, d)
                else:
                    stable += 1
        return {
            "reappeared": reappeared, "risers": risers, "faders": faders, "stable": stable,
            "top_riser": {"name": top_riser[0], "delta": top_riser[1]} if top_riser else None,
            "top_fader": {"name": top_fader[0], "delta": top_fader[1]} if top_fader else None,
        }

    bands = {"act_now": 0, "monitor": 0, "weak": 0, "none": 0}
    for c in rows:
        bands[band(c.assessed_score)] += 1

    top = rows[0] if rows else None
    # net-new = companies this run scored that were NOT already anywhere in our DB
    net_new_scored = sum(1 for c in rows if c.name not in prior)

    # Whole-database movement: EVERY company scored in ≥2 runs, first → latest
    # score. This is the "across our whole database, how many rose/fell/stable"
    # number — independent of which run is latest (Betty 2026-07-24).
    hist: dict[str, dict[str, float]] = {}
    for r in db.query(RunSnapshot).all():
        if not r.run_date:
            continue
        d = r.run_date.date().isoformat()
        slot = hist.setdefault(r.company_name, {})
        if d not in slot or (r.assessed_score or 0) > slot[d]:
            slot[d] = r.assessed_score or 0.0
    db_rose = db_fell = db_stable = db_tracked = 0
    for slots in hist.values():
        if len(slots) < 2:
            continue
        days = sorted(slots)
        delta = round(slots[days[-1]] - slots[days[0]], 1)
        db_tracked += 1
        if delta > 0:
            db_rose += 1
        elif delta < 0:
            db_fell += 1
        else:
            db_stable += 1

    # discovered-but-unscored candidates: only those NOT yet in the scored universe.
    # (After a run scores them, they drop off — the count must not stay stale.)
    discovered = 0
    try:
        import csv as _csv
        import re as _re
        from pathlib import Path as _Path
        _norm = lambda s: _re.sub(r"[^a-z0-9]", "", (s or "").lower())
        universe = {_norm(n) for (n,) in db.query(Company.name).all()}
        _p = _Path("data/csv/discovery_candidates.csv")
        if _p.exists():
            with _p.open(encoding="utf-8") as _fh:
                discovered = sum(1 for r in _csv.DictReader(_fh)
                                 if (r.get("Company Name") or "").strip()
                                 and _norm(r["Company Name"]) not in universe)
    except Exception:
        discovered = 0

    return {
        "has_run": True,
        "run_date": day.isoformat(),
        "companies": len(rows),
        "eligible": bands["act_now"],
        "bands": bands,
        "review_flagged": sum(1 for c in rows if c.review_flag),
        "top": {"name": top.name, "score": top.assessed_score} if top else None,
        "net_new_scored": net_new_scored,
        "discovered_candidates": discovered,
        "engine": "TPDL engine (rebuilt)",
        # vs the whole database (each company's previous score) — for the Sales cockpit
        "vs_db": movement(prior),
        # whole-DB movement: all companies scored more than once, first → latest
        "db_movement": {"tracked": db_tracked, "rose": db_rose,
                        "fell": db_fell, "stable": db_stable},
        # vs the original Neotek May run (cross-engine) — for the Runs page
        "neotek": {"reference_date": "2026-05-25", **movement(neotek)},
    }


# ---------------------------------------------------------------------------
# Full-detail CSV export — HTML/CSV parity (open everything in Excel)
# ---------------------------------------------------------------------------

def _history_by_company(db: Session) -> dict[str, list[dict]]:
    """Per company, its best score at each distinct run DATE, oldest → newest.
    Powers the evolution columns (previous score, delta, trajectory) in the
    export so the CSV carries the same movement story the platform shows."""
    per: dict[str, dict[str, float]] = {}
    for r in db.query(RunSnapshot).all():
        if not r.run_date:
            continue
        d = r.run_date.date().isoformat()
        s = r.assessed_score or 0.0
        slot = per.setdefault(r.company_name, {})
        if d not in slot or s > slot[d]:
            slot[d] = s
    return {name: [{"day": d, "score": days[d]} for d in sorted(days)]
            for name, days in per.items()}


# Evolution/comparison columns. They only make sense once a company has been
# scored more than once. For an all-new run (every row's first score) they'd be
# blank, so we DROP any of these that are empty across the whole export — the
# CSV then just carries the "Status = New company" marker instead of a wall of
# empty cells (Betty 2026-07-27).
_EVOLUTION_COLS = ["Previous Run Date", "Previous Score", "Delta vs Previous Run",
                   "Neotek May Score", "Delta vs May", "Score Trajectory"]

_IDENTITY_COLS = ["Company Name", "Sector", "Website", "Location", "Geo Region", "Revenue"]
_RUN_COLS = ["Run Date", "Run Label", "Status", "Assessed Score", "Coverage",
             "Outreach Eligible", "ICP Flag", "Review Flag", "Review Flag Reason"]
_NARRATIVE_COLS = ["Intelligence Summary", "Signals Found", "Signals Not Evidenced"]
_SIG_COLS = [c for i in (1, 2, 3) for c in (
    f"Signal {i} Category", f"Signal {i} What Happened", f"Signal {i} Why It Matters",
    f"Signal {i} TPDL Relevance", f"Signal {i} Confidence",
    f"Signal {i} Corroboration (0-2)", f"Signal {i} Sources", f"Signal {i} URLs")]
_CONTEXT_COLS = ["Tech Stack Summary", "Historical Context"]


def _corroboration_n(urls_str: Optional[str]) -> int:
    n = len([u for u in (urls_str or "").split(";") if u.strip()])
    return 2 if n >= 2 else (1 if n == 1 else 0)


def _export_record(c: Company, baseline: dict, history: dict) -> dict:
    """One full export row for a company — identity, score/flags, evolution vs its
    own history + Neotek, narrative, the 3 signals (sources/corroboration) and
    context. Shared by the run/universe export and the filtered view export."""
    day = c.run_date.date().isoformat() if c.run_date else None
    hist = history.get(c.name, [])
    prev = None
    for h in hist:
        if day and h["day"] < day:
            prev = h
    times = len(hist)
    neo = baseline.get(c.name)
    rec = {
        "Company Name": c.name,
        "Sector": c.sector_bucket or "",
        "Website": c.website or "",
        "Location": c.location or "",
        "Geo Region": geo_region(c.location),
        "Revenue": c.revenue or "",
        "Run Date": day or "",
        "Run Label": _date_label(day),
        "Status": "New company" if prev is None else f"Re-scored ({times} scans)",
        "Assessed Score": c.assessed_score,
        "Coverage": c.coverage,
        "Outreach Eligible": "YES" if c.outreach_eligible else "no",
        "ICP Flag": "YES" if c.icp_flag else "no",
        "Review Flag": "YES" if c.review_flag else "no",
        "Review Flag Reason": c.review_flag_reason or "",
        "Previous Run Date": prev["day"] if prev else "",
        "Previous Score": prev["score"] if prev else "",
        "Delta vs Previous Run": round((c.assessed_score or 0) - prev["score"], 1) if prev else "",
        "Neotek May Score": neo if neo is not None else "",
        "Delta vs May": round((c.assessed_score or 0) - neo, 1) if neo is not None else "",
        "Score Trajectory": " → ".join(f"{_date_label(h['day'])} {h['score']:.1f}"
                                       for h in hist) if times >= 2 else "",
        "Intelligence Summary": c.intelligence_summary or "",
        "Signals Found": c.signals_found,
        "Signals Not Evidenced": c.signals_not_evidenced or "",
        "Tech Stack Summary": c.tech_stack_summary or "",
        "Historical Context": c.historical_context or "",
    }
    for i in (1, 2, 3):
        cat = getattr(c, f"s{i}_category")
        rec[f"Signal {i} Category"] = cat
        rec[f"Signal {i} What Happened"] = getattr(c, f"s{i}_what_happened")
        rec[f"Signal {i} Why It Matters"] = getattr(c, f"s{i}_why_it_matters")
        rec[f"Signal {i} TPDL Relevance"] = getattr(c, f"s{i}_tpdl_relevance")
        rec[f"Signal {i} Confidence"] = getattr(c, f"s{i}_confidence")
        rec[f"Signal {i} Corroboration (0-2)"] = _corroboration_n(getattr(c, f"s{i}_urls")) if cat else ""
        rec[f"Signal {i} Sources"] = getattr(c, f"s{i}_sources")
        rec[f"Signal {i} URLs"] = getattr(c, f"s{i}_urls")
    return rec


def _csv_response(records: list[dict], fname: str):
    """Excel-friendly CSV (BOM + `sep=;` + semicolon) from export records. Evolution
    columns empty across ALL rows are dropped; every other group is always kept."""
    import csv
    import io
    from fastapi.responses import Response

    kept_evo = [col for col in _EVOLUTION_COLS
                if any(str(r.get(col, "")).strip() for r in records)]
    header = _IDENTITY_COLS + _RUN_COLS + kept_evo + _NARRATIVE_COLS + _SIG_COLS + _CONTEXT_COLS

    buf = io.StringIO()
    buf.write("sep=;\r\n")
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
    w.writerow(header)

    def cell(col: str, r: dict):
        v = r.get(col, "")
        if v is None:
            return ""
        if isinstance(v, float):
            return f"{v:.1f}"
        return str(v).replace("\r\n", " ").replace("\n", " ").replace("\r", " ").strip()

    for r in records:
        w.writerow([cell(col, r) for col in header])
    content = "﻿" + buf.getvalue()
    return Response(content=content, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})


@router.get("/export.csv")
def export_csv(scope: str = "run", run: Optional[str] = None, db: Session = Depends(get_db)):
    """Excel-grade export — everything the platform shows per company: identity,
    score & flags, the company context (intelligence summary, signals w/ sources
    & corroboration, tech stack, historical context), and — when the company has
    a history — its cross-run evolution. Columns that would be empty for every
    row (e.g. the comparison columns on an all-new run) are omitted.
    scope=run → one run (default: latest; ?run=YYYY-MM-DD to pick one);
    scope=all → the whole universe."""
    baseline = _neotek_baseline(db)
    history = _history_by_company(db)

    q = db.query(Company)
    fname = "tpdl_universe_full.csv"
    if scope == "run":
        target_day = run
        if not target_day:
            last_run = db.query(func.max(Company.run_date)).scalar()
            if isinstance(last_run, datetime):
                target_day = last_run.date().isoformat()
        if target_day:
            q = q.filter(func.date(Company.run_date) == target_day)
            fname = f"tpdl_run_{target_day}_full.csv"
    rows = q.order_by(Company.assessed_score.desc()).all()

    records = [_export_record(c, baseline, history) for c in rows]
    return _csv_response(records, fname)


class NamesPayload(BaseModel):
    names: list[str]
    filename: str = "tpdl_view_full.csv"
    title: str = "TPDL view"
    subtitle: str = ""


@router.post("/export_rich.csv")
def export_rich_csv(payload: NamesPayload, db: Session = Depends(get_db)):
    """Full-depth CSV for exactly the companies the client posts (a filtered view),
    IN THE POSTED ORDER — every column the run export has: summary, each signal with
    its sources & corroboration, tech stack, history, and the score trajectory (the
    curve as data). WYSIWYG richness for the Recurring/Sales views."""
    baseline = _neotek_baseline(db)
    history = _history_by_company(db)
    found = {c.name: c for c in db.query(Company).filter(Company.name.in_(payload.names[:2000])).all()}
    records = [_export_record(found[n], baseline, history) for n in payload.names if n in found]
    fname = re.sub(r"[^A-Za-z0-9._-]+", "_", payload.filename).strip("_") or "tpdl_view_full.csv"
    if not fname.endswith(".csv"):
        fname += ".csv"
    return _csv_response(records, fname)


@router.post("/view_briefs.pdf")
def view_briefs_pdf(payload: NamesPayload, db: Session = Depends(get_db)):
    """Detailed PDF for a filtered view — ONE full company brief per posted name
    (score + evolution curve, intelligence summary, signals with clickable sources,
    tech stack), in the posted order. The visual counterpart to export_rich.csv.
    Capped so a huge view can't produce a runaway document; the CSV carries all."""
    from fastapi.responses import Response
    from app.tools.company_pdf import generate_multi_brief_pdf

    CAP = 60
    names = payload.names[:CAP]
    found = {c.name: c for c in db.query(Company).filter(Company.name.in_(names)).all()}
    items: list[tuple[dict, list]] = []
    for n in names:
        c = found.get(n)
        if c is None:
            continue
        company = _serialize_company(c, baseline=_neotek_baseline(db))
        snaps = (db.query(RunSnapshot).filter(RunSnapshot.company_name == n)
                 .order_by(RunSnapshot.run_date.asc()).all())
        by_day: dict[str, float] = {}
        for s in snaps:
            day = s.run_date.date().isoformat() if s.run_date else None
            if day:
                by_day[day] = s.assessed_score or 0.0
        cur_day = c.run_date.date().isoformat() if c.run_date else None
        if cur_day:
            by_day[cur_day] = c.assessed_score or 0.0
        points = [(_date_label(day), score) for day, score in sorted(by_day.items())]
        items.append((company, points))

    pdf = generate_multi_brief_pdf(items, subject=payload.title or "TPDL view")
    fname = re.sub(r"[^A-Za-z0-9._-]+", "_", payload.filename).strip("_") or "tpdl_view_briefs.pdf"
    if not fname.endswith(".pdf"):
        fname += ".pdf"
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})


# ---------------------------------------------------------------------------
# Discovery candidates — companies FOUND on the web but NOT yet scored.
# This is the "where do NEW companies live" answer: the scored table only holds
# the re-scored existing universe; genuinely new names sit here until a (paid)
# scoring run promotes them. found ≠ scored — the UI must never blur the two.
# ---------------------------------------------------------------------------

_THEME_LABELS = {
    "leadership_change": "Leadership change",
    "hiring": "Hiring",
    "ma_expansion": "M&A / Expansion",
    "pe_event": "PE event",
    "digital_initiative": "Digital initiative",
    "org_restructuring": "Org restructuring",
    "earnings_call_digital": "Earnings-call digital priority",
}


@router.get("/candidates")
def discovery_candidates(db: Session = Depends(get_db)) -> dict:
    """Read data/csv/discovery_candidates.csv (the discovery step's output) and
    flag which names are genuinely new to the scored universe."""
    import csv
    import re
    from pathlib import Path

    path = Path("data/csv/discovery_candidates.csv")
    if not path.exists():
        return {"found": False, "count": 0, "candidates": [], "by_theme": []}

    def norm(s: str) -> str:
        return re.sub(r"[^a-z0-9]", "", (s or "").lower())

    universe = {norm(n) for (n,) in db.query(Company.name).all()}

    from app.tools.icp import assess_icp

    # Optional comparison vs Friday's list (data/csv/discovery_comparison.csv,
    # written by scripts/compare_discoveries.py). Kept SEPARATE from the runs
    # (Betty 2026-07-23): shows which candidates are common / new, no merge.
    comparison: dict[str, str] = {}
    comp_path = Path("data/csv/discovery_comparison.csv")
    if comp_path.exists():
        with comp_path.open(encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                cname = (r.get("Company") or "").strip()
                status = (r.get("Status") or "").strip()
                if cname and status:
                    comparison[norm(cname)] = status

    rows: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            name = (r.get("Company Name") or "").strip()
            if not name:
                continue
            theme = (r.get("Theme") or "").strip()
            icp = assess_icp(name)   # name-only at discovery — flags CDMO/CRO/consultancy/etc.
            rows.append({
                "company": name,
                "hq": (r.get("HQ / City") or "").strip(),
                "theme": theme,
                "theme_label": _THEME_LABELS.get(theme, theme or "—"),
                "source_url": (r.get("Source URL") or "").strip(),
                "already_in_universe": norm(name) in universe,
                "scored": False,        # discovery output is never scored
                "out_of_icp": icp["out_of_scope"],
                "icp_reason": icp["reason"],
                # vs Friday: 'common' (both lists) | 'new' (only this run) | None
                "vs_friday": comparison.get(norm(name)),
            })

    from collections import Counter
    counts = Counter(r["theme"] for r in rows)
    by_theme = [
        {"theme": t, "theme_label": _THEME_LABELS.get(t, t), "count": n}
        for t, n in counts.most_common()
    ]
    new_count = sum(1 for r in rows if not r["already_in_universe"])
    scored_count = sum(1 for r in rows if r["already_in_universe"])
    out_of_icp = sum(1 for r in rows if r["out_of_icp"])

    # Append-only discovery archive (pipeline/discovery.py) — the anti-leak net.
    # Every name ever surfaced is logged here even after discovery_candidates.csv
    # is overwritten, so we can always prove nothing fell through: any archived
    # name NOT in the scored universe is still waiting.
    archive = {"ever_discovered": 0, "never_scored": 0, "never_scored_names": []}
    arch_path = Path("data/csv/discovery_archive.csv")
    if arch_path.exists():
        with arch_path.open(encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                nm = (r.get("Company Name") or "").strip()
                if not nm:
                    continue
                archive["ever_discovered"] += 1
                if norm(nm) not in universe:
                    archive["never_scored"] += 1
                    if len(archive["never_scored_names"]) < 100:
                        archive["never_scored_names"].append({
                            "company": nm,
                            "first_discovered": (r.get("First Discovered") or "").strip(),
                            "theme": (r.get("Theme") or "").strip(),
                        })
    comp_summary = None
    if comparison:
        # 'dropped' = only in Friday, so not among these rows — count from the map.
        comp_summary = {
            "found": True,
            "common": sum(1 for s in comparison.values() if s == "common"),
            "new": sum(1 for s in comparison.values() if s == "new"),
            "dropped": sum(1 for s in comparison.values() if s == "dropped"),
        }
    return {
        "found": True,
        "count": len(rows),
        "new_to_universe": new_count,
        "scored": scored_count,          # discovered names that have since been scored
        "out_of_icp": out_of_icp,
        "in_icp": len(rows) - out_of_icp,
        "candidates": rows,
        "by_theme": by_theme,
        "comparison": comp_summary,
        "archive": archive,
    }


# ---------------------------------------------------------------------------
# Recurring — companies that keep coming back across our scan DATES (May 25,
# Jul 17, Jul 23…). Grouped by run_date, not by batch id, so the two Jul 23
# batches count as one scan (Betty's "3× : mai · Jul 17 · Jul 23" idea). A
# company recurring across runs = sustained relevance worth watching.
# ---------------------------------------------------------------------------

def _date_label(iso_day: str) -> str:
    """'2026-07-23' → 'Jul 23'. Falls back to the raw string if unparseable."""
    try:
        return datetime.strptime(iso_day, "%Y-%m-%d").strftime("%b %d").replace(" 0", " ")
    except (ValueError, TypeError):
        return iso_day or "—"


@router.get("/recurring")
def recurring(db: Session = Depends(get_db)) -> dict:
    """Companies present in ≥2 distinct run DATES, with their per-date score.
    Sorted by how many runs they appear in (desc), then latest score (desc)."""
    # Collect, per company, the best score seen on each distinct run_date.
    per_company: dict[str, dict[str, dict]] = {}
    for r in db.query(RunSnapshot).all():
        day = (r.run_date.date().isoformat() if r.run_date else "unknown")
        slot = per_company.setdefault(r.company_name, {})
        prev = slot.get(day)
        # If a date has several batches, keep the one that actually scored it
        # (highest score) — avoids a flaky 0 masking a real score same day.
        if prev is None or (r.assessed_score or 0) > prev["score"]:
            slot[day] = {"day": day, "label": _date_label(day),
                         "score": round(r.assessed_score or 0.0, 1),
                         "eligible": bool(r.outreach_eligible)}

    # Current ICP flag / sector for context (companies table = latest state).
    meta = {c.name: c for c in db.query(Company).all()}

    all_days = sorted({d for slots in per_company.values() for d in slots})
    rows = []
    for name, slots in per_company.items():
        if len(slots) < 2:                       # recurring = seen in ≥2 dates
            continue
        runs = sorted(slots.values(), key=lambda s: s["day"])
        c = meta.get(name)
        first, last = runs[0]["score"], runs[-1]["score"]
        rows.append({
            "company": name,
            "count": len(runs),
            "runs": runs,                         # chronological, each {day,label,score,eligible}
            "days": [r["day"] for r in runs],     # for quick client-side matching
            "latest_score": last,
            "delta_first_last": round(last - first, 1),
            "out_of_icp": bool(c.icp_flag) if c else False,
            "sector_bucket": (c.sector_bucket if c else None),
            "location": (c.location if c else None),
        })
    rows.sort(key=lambda r: (r["count"], r["latest_score"]), reverse=True)

    return {
        "count": len(rows),
        "all_days": [{"day": d, "label": _date_label(d)} for d in all_days],
        "max_runs": len(all_days),
        "companies": rows,
    }


# ---------------------------------------------------------------------------
# Weekly review batch — 70/30 Europe/world curation (chantier 3/4, 2026-09-01
# meeting recap). Nathalie's personal weekly reading list, NOT Maya's
# /shortlist (Inès's SDR batch hand-off keeps consuming that one unchanged —
# see app/tools/shortlist.py's own "never disagree" contract).
# ---------------------------------------------------------------------------

@router.get("/weekly-review")
def weekly_review(n: int = 10, db: Session = Depends(get_db)) -> dict:
    from app.tools.curation import weekly_review_batch

    rows = (db.query(Company).filter(Company.icp_flag.is_(False))
            .order_by(Company.assessed_score.desc()).all())
    baseline = _neotek_baseline(db)
    serialized = [_serialize_company(r, baseline) for r in rows]
    batch = weekly_review_batch(serialized, n)
    core_n = sum(1 for c in batch if c["market_tier"] == "core")
    return {
        "n_requested": n,
        "n_returned": len(batch),
        "core_count": core_n,
        "world_count": len(batch) - core_n,
        "companies": batch,
    }


# ---------------------------------------------------------------------------
# Mega-cap trend-watch (chantier 2/4, `pipeline/recap.py --recap`) — read-only,
# groups MegaCapRecap rows by company with their run history for the "Mega-cap
# watch" tab. No scoring concept here (see recap.py's own docstring).
# ---------------------------------------------------------------------------

@router.get("/megacap-recap")
def megacap_recap(db: Session = Depends(get_db)) -> dict:
    from app.models import MegaCapRecap

    rows = (db.query(MegaCapRecap)
            .order_by(MegaCapRecap.company_name, MegaCapRecap.run_date).all())
    by_company: dict[str, dict] = {}
    for r in rows:
        slot = by_company.setdefault(r.company_name, {
            "company_name": r.company_name, "runs": [], "facts": [],
        })
        day = r.run_date.date().isoformat() if r.run_date else None
        if day and day not in slot["runs"]:
            slot["runs"].append(day)
        slot["facts"].append({
            "category": r.category,
            "summary": r.summary_text,
            "quote": r.quote,
            "source": r.source,
            "url": r.url,
            "event_date": r.event_date.date().isoformat() if r.event_date else None,
            "run_date": day,
        })
    companies = sorted(by_company.values(), key=lambda c: c["company_name"])
    for c in companies:
        c["runs"].sort()
        c["fact_count"] = len(c["facts"])
    return {"companies": companies, "total_facts": len(rows)}


# ---------------------------------------------------------------------------
# Executive moves (chantier 4/4, `pipeline/exec_moves.py`) — read + the two
# human decisions (approve/dismiss). Shares its state-transition logic with
# Inès's `/moves` chat command via app/tools/moves.py, so the dashboard UI and
# the chat can never disagree about what "approve"/"dismiss" means.
# ---------------------------------------------------------------------------

@router.get("/moves")
def list_moves(status: Optional[str] = None, db: Session = Depends(get_db)) -> dict:
    from app.models import ExecutiveMove
    from app.tools.moves import serialize_move

    q = db.query(ExecutiveMove)
    if status:
        q = q.filter(ExecutiveMove.status == status)
    rows = q.order_by(ExecutiveMove.discovered_at.desc()).limit(200).all()
    return {"count": len(rows), "moves": [serialize_move(m) for m in rows]}


@router.post("/moves/{move_id}/approve")
def approve_move_endpoint(move_id: int, db: Session = Depends(get_db)) -> dict:
    from app.tools.moves import approve_move, serialize_move

    m, outcome = approve_move(db, move_id)
    if outcome == "not_found":
        raise HTTPException(status_code=404, detail=f"No executive move with id {move_id}")
    return {"outcome": outcome, "move": serialize_move(m)}


@router.post("/moves/{move_id}/dismiss")
def dismiss_move_endpoint(move_id: int, db: Session = Depends(get_db)) -> dict:
    from app.tools.moves import dismiss_move, serialize_move

    m, outcome = dismiss_move(db, move_id)
    if outcome == "not_found":
        raise HTTPException(status_code=404, detail=f"No executive move with id {move_id}")
    return {"outcome": outcome, "move": serialize_move(m)}


# ---------------------------------------------------------------------------
# Run comparison — pick any two runs (a "from" and a "to") and see what moved,
# like filtering a bank statement to a date range. Today there are two runs
# (Neotek May reference + the July TPDL run); the moment more runs land, the
# pickers grow automatically — nothing here is hard-coded to two.
# ---------------------------------------------------------------------------

def _run_label(day: Optional[str]) -> str:
    engine = "Neotek" if day == NEOTEK_REFERENCE_DATE else "TPDL"
    return f"{engine} · {day}" if day else engine


def _runs_by_date(db: Session) -> dict[str, dict[str, float]]:
    """{iso_date: {company: best_score that day}}. Groups by SCAN DATE, not by
    import batch — so the three 23 Jul batches count as ONE '23 Jul' run (same
    rule as the Recurring page). Best score per company covers same-day re-scores."""
    by_date: dict[str, dict[str, float]] = {}
    for r in db.query(RunSnapshot).all():
        if not r.run_date:
            continue
        d = r.run_date.date().isoformat()
        slot = by_date.setdefault(d, {})
        s = r.assessed_score or 0.0
        if r.company_name not in slot or s > slot[r.company_name]:
            slot[r.company_name] = s
    return by_date


@router.get("/runs")
def list_runs(db: Session = Depends(get_db)) -> dict:
    """Every scan DATE in history, oldest → newest, for the comparison pickers.
    One entry per date (batches of the same day are merged), INCLUDING the Neotek
    May reference. The date string is the run identifier used by /compare."""
    by_date = _runs_by_date(db)
    runs = [{
        "run_id":    d,                       # the date IS the identifier now
        "run_date":  d,
        "label":     _run_label(d),
        "companies": len(names),
        "is_neotek": d == NEOTEK_REFERENCE_DATE,
    } for d, names in by_date.items()]
    runs.sort(key=lambda r: r["run_date"] or "")
    return {"runs": runs, "count": len(runs)}


@router.get("/baseline")
def baseline_scores(run: str, db: Session = Depends(get_db)) -> dict:
    """Per-company scores for ONE scan date, so the Sales Δ column can be rebased
    to any run the user picks in the header dropdown (default = the first run)."""
    by_date = _runs_by_date(db)
    return {"run": run, "scores": by_date.get(run, {})}


@router.get("/compare")
def compare_runs(
    from_run: str,
    to_run: str,
    span: str = "two",
    db: Session = Depends(get_db),
) -> dict:
    """Per-company movement between two scan DATES. `from_run`/`to_run` are date
    strings (see /runs). Two modes:
    - span="two"  (default): compares ONLY the two endpoint runs.
    - span="full": includes EVERY run between from and to. Each company is tracked
      from its FIRST to its LAST appearance in the range, carrying the full
      trajectory across the middle runs (so e.g. Neotek→23 Jul folds in 17 Jul).
    Status: new (a single data point in the span), rising / fading / stable."""
    by_date = _runs_by_date(db)
    a = by_date.get(from_run, {})
    b = by_date.get(to_run, {})
    if not b and not a:
        raise HTTPException(status_code=404, detail="Unknown run id(s)")

    companies = []
    span_dates: list[str] = []

    if span == "full":
        # every run date within [from_run, to_run] inclusive, chronological
        lo, hi = sorted((from_run, to_run))
        span_dates = sorted(d for d in by_date if lo <= d <= hi)
        for name in sorted({n for d in span_dates for n in by_date[d]}):
            appearances = [(d, by_date[d][name]) for d in span_dates if name in by_date[d]]
            traj = [{"label": _run_label(d), "score": s} for d, s in appearances]
            fa = appearances[0][1]
            fb = appearances[-1][1]
            if len(appearances) >= 2:
                delta = round(fb - fa, 1)
                status = "rising" if delta > 0 else "fading" if delta < 0 else "stable"
            else:                 # a single data point in the span — no movement
                delta, status = None, "new"
            companies.append({
                "company": name, "from_score": fa, "to_score": fb,
                "delta": delta, "status": status, "trajectory": traj,
            })
    else:
        for name in sorted(set(a) | set(b)):
            fa = a.get(name)
            fb = b.get(name)
            if fa is not None and fb is not None:
                delta = round(fb - fa, 1)
                status = "rising" if delta > 0 else "fading" if delta < 0 else "stable"
            elif fb is not None:      # in `to` only
                delta, status = None, "new"
            else:                     # in `from` only
                delta, status = None, "dropped"
            companies.append({
                "company":    name,
                "from_score": fa,
                "to_score":   fb,
                "delta":      delta,
                "status":     status,
                "trajectory": [],
            })

    def _cnt(s: str) -> int:
        return sum(1 for c in companies if c["status"] == s)

    both = [c for c in companies if c["delta"] is not None]
    top_riser = max((c for c in both if c["delta"] > 0), key=lambda c: c["delta"], default=None)
    top_fader = min((c for c in both if c["delta"] < 0), key=lambda c: c["delta"], default=None)

    # run metadata for labels
    runs = {r["run_id"]: r for r in list_runs(db)["runs"]}
    return {
        "span": span,
        "span_runs": [{"run_id": d, "label": _run_label(d)} for d in span_dates],
        "from": runs.get(from_run, {"run_id": from_run}),
        "to":   runs.get(to_run,   {"run_id": to_run}),
        "summary": {
            "new":     _cnt("new"),
            "dropped": _cnt("dropped"),
            "rising":  _cnt("rising"),
            "fading":  _cnt("fading"),
            "stable":  _cnt("stable"),
            "common":  len(both),
            "top_riser": {"company": top_riser["company"], "delta": top_riser["delta"]} if top_riser else None,
            "top_fader": {"company": top_fader["company"], "delta": top_fader["delta"]} if top_fader else None,
        },
        "companies": companies,
    }
