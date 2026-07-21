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
from app.models import Company, RunSnapshot
from app.tools.radars import geo_region

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/intel", tags=["intel"])

# The 25/05 run is the ORIGINAL Neotek engine (external reference). Every company
# in our own July run was also in that Neotek run, so we can show each company's
# movement since Neotek. NB: the two runs come from DIFFERENT engines (Neotek in
# May, TPDL's rebuilt engine in July), so a delta mixes a real change in signal
# with an engine change — the UI is explicit about that caveat.
NEOTEK_REFERENCE_RUN = "cb97cf5d50d2"


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


def _serialize_company(c: Company, baseline: Optional[dict[str, float]] = None) -> dict:
    signals = [b for b in (_signal_block(c, i) for i in (1, 2, 3)) if b]
    not_evidenced = [
        s.strip() for s in (c.signals_not_evidenced or "").split(";") if s.strip()
    ]
    # Movement since the Neotek May reference run.
    neotek = None
    delta = None
    reappeared = False
    if baseline is not None and c.name in baseline:
        neotek = baseline[c.name]
        delta = round((c.assessed_score or 0.0) - neotek, 1)
        reappeared = True
    return {
        "name":          c.name,
        "sector":        c.sector,
        "sector_bucket": c.sector_bucket,
        "website":       c.website,
        "location":      c.location,
        "geo_region":    geo_region(c.location),
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
        # Neotek → now movement
        "neotek_score":       neotek,
        "delta":              delta,
        "reappeared":         reappeared,
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
    return [_serialize_company(r, baseline) for r in rows]


@router.get("/companies/{name}")
def get_company(name: str, db: Session = Depends(get_db)) -> dict:
    c = db.get(Company, name)
    if c is None:
        raise HTTPException(status_code=404, detail=f"Company '{name}' not found")
    return _serialize_company(c, _neotek_baseline(db))


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
    baseline = _neotek_baseline(db)

    def band(s: float) -> str:
        s = s or 0
        if s >= 8: return "act_now"
        if s >= 5: return "monitor"
        if s >= 1: return "weak"
        return "none"

    bands = {"act_now": 0, "monitor": 0, "weak": 0, "none": 0}
    reappeared = risers = faders = stable = 0
    top_riser = top_fader = None
    for c in rows:
        bands[band(c.assessed_score)] += 1
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

    top = rows[0] if rows else None
    # net-new SCORED this run = companies in the run that Neotek never had
    net_new_scored = sum(1 for c in rows if c.name not in baseline)

    # discovered-but-unscored candidates waiting in the discovery step's output
    discovered = 0
    try:
        import csv as _csv
        from pathlib import Path as _Path
        _p = _Path("data/csv/discovery_candidates.csv")
        if _p.exists():
            with _p.open(encoding="utf-8") as _fh:
                discovered = sum(1 for r in _csv.DictReader(_fh)
                                 if (r.get("Company Name") or "").strip())
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
        "neotek": {
            "reference_date": "2026-05-25",
            "reappeared": reappeared,
            "risers": risers,
            "faders": faders,
            "stable": stable,
            "top_riser": {"name": top_riser[0], "delta": top_riser[1]} if top_riser else None,
            "top_fader": {"name": top_fader[0], "delta": top_fader[1]} if top_fader else None,
        },
    }


# ---------------------------------------------------------------------------
# Full-detail CSV export — HTML/CSV parity (open everything in Excel)
# ---------------------------------------------------------------------------

_EXPORT_HEADER = [
    "Company Name", "Sector", "Sector Bucket", "Website", "Location", "Revenue",
    "Assessed Score", "Neotek May Score", "Delta vs Neotek", "Reappeared",
    "Coverage", "Outreach Eligible", "Intelligence Summary",
    "Signals Found", "Signals Not Evidenced",
    "Signal 1 Category", "Signal 1 What Happened", "Signal 1 Why It Matters",
    "Signal 1 TPDL Relevance", "Signal 1 Confidence", "Signal 1 Sources", "Signal 1 URLs",
    "Signal 2 Category", "Signal 2 What Happened", "Signal 2 Why It Matters",
    "Signal 2 TPDL Relevance", "Signal 2 Confidence", "Signal 2 Sources", "Signal 2 URLs",
    "Signal 3 Category", "Signal 3 What Happened", "Signal 3 Why It Matters",
    "Signal 3 TPDL Relevance", "Signal 3 Confidence", "Signal 3 Sources", "Signal 3 URLs",
    "Tech Stack Summary", "Historical Context", "ICP Flag",
    "Review Flag", "Review Flag Reason", "Run Date",
]


@router.get("/export.csv")
def export_csv(scope: str = "run", db: Session = Depends(get_db)):
    """Excel-grade export — same fields the HTML shows, plus the Neotek delta.
    scope=run → latest run only (default); scope=all → the whole universe."""
    import csv
    import io
    from fastapi.responses import Response

    baseline = _neotek_baseline(db)
    q = db.query(Company)
    fname = "tpdl_universe.csv"
    if scope == "run":
        last_run = db.query(func.max(Company.run_date)).scalar()
        if isinstance(last_run, datetime):
            day = last_run.date().isoformat()
            q = q.filter(func.date(Company.run_date) == day)
            fname = f"tpdl_run_{day}.csv"
    rows = q.order_by(Company.assessed_score.desc()).all()

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(_EXPORT_HEADER)
    for c in rows:
        neo = baseline.get(c.name)
        delta = round((c.assessed_score or 0) - neo, 1) if neo is not None else ""
        row = [
            c.name, c.sector, c.sector_bucket, c.website, c.location, c.revenue,
            c.assessed_score, neo if neo is not None else "", delta,
            "YES" if c.name in baseline else "no",
            c.coverage, "YES" if c.outreach_eligible else "no", c.intelligence_summary,
            c.signals_found, c.signals_not_evidenced,
        ]
        for i in (1, 2, 3):
            row += [getattr(c, f"s{i}_category"), getattr(c, f"s{i}_what_happened"),
                    getattr(c, f"s{i}_why_it_matters"), getattr(c, f"s{i}_tpdl_relevance"),
                    getattr(c, f"s{i}_confidence"), getattr(c, f"s{i}_sources"),
                    getattr(c, f"s{i}_urls")]
        row += [c.tech_stack_summary, c.historical_context,
                "YES" if c.icp_flag else "no",
                "YES" if c.review_flag else "no", c.review_flag_reason,
                c.run_date.date().isoformat() if c.run_date else ""]
        w.writerow(row)

    return Response(content=buf.getvalue(), media_type="text/csv",
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

    rows: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            name = (r.get("Company Name") or "").strip()
            if not name:
                continue
            theme = (r.get("Theme") or "").strip()
            rows.append({
                "company": name,
                "theme": theme,
                "theme_label": _THEME_LABELS.get(theme, theme or "—"),
                "source_url": (r.get("Source URL") or "").strip(),
                "already_in_universe": norm(name) in universe,
                "scored": False,        # discovery output is never scored
            })

    from collections import Counter
    counts = Counter(r["theme"] for r in rows)
    by_theme = [
        {"theme": t, "theme_label": _THEME_LABELS.get(t, t), "count": n}
        for t, n in counts.most_common()
    ]
    new_count = sum(1 for r in rows if not r["already_in_universe"])
    return {
        "found": True,
        "count": len(rows),
        "new_to_universe": new_count,
        "candidates": rows,
        "by_theme": by_theme,
    }


# ---------------------------------------------------------------------------
# Run comparison — pick any two runs (a "from" and a "to") and see what moved,
# like filtering a bank statement to a date range. Today there are two runs
# (Neotek May reference + the July TPDL run); the moment more runs land, the
# pickers grow automatically — nothing here is hard-coded to two.
# ---------------------------------------------------------------------------

def _run_label(run_id: str, day: Optional[str]) -> str:
    engine = "Neotek" if run_id == NEOTEK_REFERENCE_RUN else "TPDL"
    return f"{engine} · {day}" if day else engine


@router.get("/runs")
def list_runs(db: Session = Depends(get_db)) -> dict:
    """Every run in history, oldest → newest, for the comparison pickers.
    INCLUDES the Neotek May reference (the user explicitly wants to diff
    against it), unlike the /runs traceability page which tracks TPDL only."""
    by_run: dict[str, list[RunSnapshot]] = {}
    for r in db.query(RunSnapshot).all():
        by_run.setdefault(r.import_run_id, []).append(r)
    runs = []
    for run_id, rows in by_run.items():
        dates = [r.run_date for r in rows if r.run_date]
        day = min(dates).date().isoformat() if dates else None
        runs.append({
            "run_id":    run_id,
            "run_date":  day,
            "label":     _run_label(run_id, day),
            "companies": len(rows),
            "is_neotek": run_id == NEOTEK_REFERENCE_RUN,
        })
    runs.sort(key=lambda r: r["run_date"] or "")
    return {"runs": runs, "count": len(runs)}


@router.get("/compare")
def compare_runs(
    from_run: str,
    to_run: str,
    db: Session = Depends(get_db),
) -> dict:
    """Per-company movement between ANY two runs. `from_run` is the baseline,
    `to_run` the later period. Returns each company with its from/to score,
    the delta, and a status: new (only in `to`), dropped (only in `from`),
    rising / fading / stable (present in both)."""
    def scores(run_id: str) -> dict[str, float]:
        return {r.company_name: (r.assessed_score or 0.0) for r in
                db.query(RunSnapshot).filter(RunSnapshot.import_run_id == run_id).all()}

    a = scores(from_run)
    b = scores(to_run)
    if not b and not a:
        raise HTTPException(status_code=404, detail="Unknown run id(s)")

    companies = []
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
        })

    def _cnt(s: str) -> int:
        return sum(1 for c in companies if c["status"] == s)

    both = [c for c in companies if c["delta"] is not None]
    top_riser = max((c for c in both if c["delta"] > 0), key=lambda c: c["delta"], default=None)
    top_fader = min((c for c in both if c["delta"] < 0), key=lambda c: c["delta"], default=None)

    # run metadata for labels
    runs = {r["run_id"]: r for r in list_runs(db)["runs"]}
    return {
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
