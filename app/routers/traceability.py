"""Traceability — see every run, what Hugo produced and what Maya read of it,
with per-run CSV downloads and a plain-English recap. All data comes from
`RunSnapshot` (the append-only per-run history), so the page is honest about
what was actually stored, never reconstructed.
"""
from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.config import TEMPLATES_DIR
from app.database import get_db
from app.models import RunSnapshot

router = APIRouter(tags=["traceability"])
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# The 25/05 run is the ORIGINAL Neotek engine (external reference), not a run of
# TPDL's own rebuilt engine. Traceability tracks OUR engine only — comparing our
# July output against Neotek-May would be apples-to-oranges (different engines),
# so the Neotek run is excluded from this page and from trajectory comparisons.
NEOTEK_REFERENCE_RUN = "cb97cf5d50d2"
NEOTEK_REFERENCE_DATE = "2026-05-25"   # the Neotek run's date (its identity here is the date)

# SharePoint folder where run results are collected (opens in the browser where
# the user is already logged in). Override with SHAREPOINT_RESULTS_URL in .env.
import os
SHAREPOINT_FOLDER_URL = os.environ.get("SHAREPOINT_RESULTS_URL", (
    "https://netorgft10677151.sharepoint.com/sites/"
    "LinkedInEmailCampaignandcontent-ContentProductionforLinkeIn/Shared%20Documents/"
    "Forms/AllItems.aspx?id=%2Fsites%2FLinkedInEmailCampaignandcontent%2D"
    "ContentProductionforLinkeIn%2FShared%20Documents%2FContent%20Production%20for%20"
    "LinkeIn%2F03%5FGen%20AI%20Automation%20Hub%2FTPDL%20AGENTS%20PILOT"
    "&viewid=8a730f10%2D3831%2D4126%2Da97c%2De7679be5831d"))


# ─────────────────────────────────────────────────────────────────────────────
# Data helpers
# ─────────────────────────────────────────────────────────────────────────────

def _date_snapshots(db: Session, day: str) -> dict[str, RunSnapshot]:
    """Best snapshot per company for a run DATE — dedups a company scored in more
    than one import batch the SAME day (keeps the highest-scoring snapshot). This
    is what makes the page show ONE run per date, not one per import batch."""
    best: dict[str, RunSnapshot] = {}
    for r in db.query(RunSnapshot).all():
        if not r.run_date or r.run_date.date().isoformat() != day:
            continue
        cur = best.get(r.company_name)
        if cur is None or (r.assessed_score or 0) > (cur.assessed_score or 0):
            best[r.company_name] = r
    return best


def _runs_ordered(db: Session) -> list[dict]:
    """One row per run DATE (same-date import batches unified into one), oldest →
    newest. The Neotek May reference is excluded. Companies are deduped within a
    date; 'eligible' = score ≥ 8. The run identity here is the DATE string."""
    by_day: dict[str, dict[str, RunSnapshot]] = {}
    batches: dict[str, set] = {}
    for r in db.query(RunSnapshot).all():
        if not r.run_date:
            continue
        day = r.run_date.date().isoformat()
        if day == NEOTEK_REFERENCE_DATE:
            continue                       # exclude the external Neotek reference
        d = by_day.setdefault(day, {})
        cur = d.get(r.company_name)
        if cur is None or (r.assessed_score or 0) > (cur.assessed_score or 0):
            d[r.company_name] = r
        batches.setdefault(day, set()).add(r.import_run_id)
    out = []
    for day, snaps in by_day.items():
        scores = [s.assessed_score or 0 for s in snaps.values()]
        out.append({
            "run_id": day,                 # identity = the date (unifies same-day batches)
            "run_date": day,
            "companies": len(snaps),
            "eligible": sum(1 for v in scores if v >= 8),
            "top_score": max(scores) if scores else 0,
            "batches": len(batches.get(day, set())),
        })
    out.sort(key=lambda x: x["run_date"] or "")
    return out


def _top_company(db: Session, day: str) -> tuple[str, float] | None:
    snaps = _date_snapshots(db, day)
    if not snaps:
        return None
    name = max(snaps, key=lambda n: snaps[n].assessed_score or 0)
    return (name, float(snaps[name].assessed_score or 0))


def _hugo_recap(db: Session, run: dict) -> str:
    top = _top_company(db, run["run_id"])
    top_str = f"; top scorer {top[0]} at {top[1]:.1f}" if top else ""
    return (f"Hugo scored {run['companies']} companies on {run['run_date'] or 'an unknown date'}; "
            f"{run['eligible']} are outreach-eligible (score ≥ 8){top_str}.")


def _maya_recap(db: Session, runs: list[dict], run: dict) -> str:
    """Maya reads ACROSS runs — recurrence needs ≥2 runs in history."""
    idx = next((i for i, r in enumerate(runs) if r["run_id"] == run["run_id"]), 0)
    if idx == 0:
        return ("Maya: this is the earliest run in history — recurrence and "
                "trajectory activate from the next run onward.")
    prev = runs[idx - 1]
    # companies present in BOTH run dates, with score deltas
    cur = _scores_for(db, run["run_id"])
    old = _scores_for(db, prev["run_id"])
    common = [(n, cur[n] - old[n]) for n in cur if n in old]
    if not common:
        return (f"Maya: no company overlaps with the previous run "
                f"({prev['run_date']}), so no trajectory can be compared.")
    risers = [c for c in common if c[1] > 0]
    faders = [c for c in common if c[1] < 0]
    top_r = max(common, key=lambda c: c[1])
    top_f = min(common, key=lambda c: c[1])
    return (f"Maya: {len(common)} companies recur vs the previous run "
            f"({prev['run_date']}) — {len(risers)} rising, {len(faders)} fading. "
            f"Top riser {top_r[0]} ({top_r[1]:+.1f}); top fader {top_f[0]} ({top_f[1]:+.1f}).")


# ─────────────────────────────────────────────────────────────────────────────
# Page + JSON
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/runs")
def runs_page() -> RedirectResponse:
    """Merged into /intel (Runs tab) on 2026-08-31 — kept as a redirect so old
    links/bookmarks/memory notes pointing at /runs keep working."""
    return RedirectResponse(url="/intel?tab=runs", status_code=302)


def _scores_for(db: Session, day: str) -> dict[str, float]:
    """Company → score for a run DATE (deduped across same-day batches)."""
    return {n: (s.assessed_score or 0) for n, s in _date_snapshots(db, day).items()}


def _latest_tpdl_run(db: Session) -> dict | None:
    """The newest run that ISN'T the Neotek reference."""
    runs = _runs_ordered(db)   # excludes Neotek, oldest→newest
    return runs[-1] if runs else None


def _neotek_compare(db: Session) -> dict:
    """Companies present in BOTH the Neotek May reference and the latest TPDL
    run — each with its Neotek score, its TPDL score and the delta. Answers
    'how did our own engine re-score the companies Neotek already covered?'"""
    tpdl = _latest_tpdl_run(db)
    if tpdl is None:
        return {"available": False, "reason": "no TPDL run yet"}
    neo = _scores_for(db, NEOTEK_REFERENCE_DATE)
    cur = _scores_for(db, tpdl["run_id"])
    if not neo:
        return {"available": False, "reason": "no Neotek reference in history"}
    common = []
    for name in cur:
        if name in neo:
            delta = round(cur[name] - neo[name], 1)
            common.append({
                "company": name, "neotek": neo[name], "tpdl": cur[name],
                "delta": delta,
                "movement": "higher" if delta > 0 else "lower" if delta < 0 else "same",
            })
    common.sort(key=lambda c: c["delta"])   # biggest drops first, biggest rises last
    return {
        "available": True,
        "neotek_run": {"label": "Neotek (25/05)", "companies": len(neo)},
        "tpdl_run": {"label": f"TPDL ({tpdl['run_date']})", "companies": tpdl["companies"]},
        "common_count": len(common),
        "tpdl_only": sorted(n for n in cur if n not in neo),
        "companies": common,
    }


@router.get("/api/runs/compare")
def api_compare(db: Session = Depends(get_db)) -> dict:
    return _neotek_compare(db)


@router.get("/api/runs/compare.csv")
def compare_csv(db: Session = Depends(get_db)) -> Response:
    cmp = _neotek_compare(db)
    rows = [[c["company"], c["neotek"], c["tpdl"], f"{c['delta']:+.1f}", c["movement"]]
            for c in cmp.get("companies", [])]
    return _csv_response(
        rows, ["Company", "Neotek score (25/05)", "TPDL score (Jul)", "Delta", "Movement"],
        "neotek_vs_tpdl.csv")


@router.get("/api/runs")
def api_runs(db: Session = Depends(get_db)) -> dict:
    runs = _runs_ordered(db)
    cards = []
    for run in reversed(runs):   # newest first for display
        cards.append({
            **run,
            "hugo_recap": _hugo_recap(db, run),
            "maya_recap": _maya_recap(db, runs, run),
            "hugo_csv": f"/api/runs/{run['run_id']}/hugo.csv",
            "maya_csv": f"/api/runs/{run['run_id']}/maya.csv",
            "combined_csv": f"/api/runs/{run['run_id']}/combined.csv",
        })
    return {"runs": cards, "count": len(cards), "sharepoint_url": SHAREPOINT_FOLDER_URL}


# ─────────────────────────────────────────────────────────────────────────────
# Trajectory helper (shared by maya.csv and combined.csv)
# ─────────────────────────────────────────────────────────────────────────────

def _trajectory(db: Session, day: str) -> dict[str, dict]:
    """Per-company movement vs the previous TPDL-engine run DATE (Neotek excluded)."""
    runs = _runs_ordered(db)
    idx = next((i for i, r in enumerate(runs) if r["run_id"] == day), 0)
    cur = _scores_for(db, day)
    old = _scores_for(db, runs[idx - 1]["run_id"]) if idx > 0 else {}
    out = {}
    for name, score in cur.items():
        if name in old:
            delta = score - old[name]
            out[name] = {"trajectory": f"{old[name]}→{score}",
                         "movement": "RISING" if delta > 0 else "FADING" if delta < 0 else "stable",
                         "delta": f"{delta:+.1f}"}
        else:
            out[name] = {"trajectory": f"{score} (new)", "movement": "NEW", "delta": ""}
    return out


# ─────────────────────────────────────────────────────────────────────────────
# CSV downloads
# ─────────────────────────────────────────────────────────────────────────────

def _csv_response(rows: list[list], header: list[str], filename: str) -> Response:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    w.writerows(rows)
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/api/runs/{run_id}/hugo.csv")
def hugo_csv(run_id: str, db: Session = Depends(get_db)) -> Response:
    """Hugo's output for one run DATE: every company + its score, ranked."""
    snaps = sorted(_date_snapshots(db, run_id).values(),
                   key=lambda r: -(r.assessed_score or 0))
    data = [[r.company_name, r.assessed_score, r.coverage,
             "YES" if r.outreach_eligible else "no", r.signals_found]
            for r in snaps]
    return _csv_response(data,
                         ["Company", "Assessed Score", "Coverage",
                          "Outreach Eligible", "Signals Found"],
                         f"hugo_run_{run_id}.csv")


@router.get("/api/runs/{run_id}/maya.csv")
def maya_csv(run_id: str, db: Session = Depends(get_db)) -> Response:
    """Maya's read for one run DATE: each company's trajectory vs the previous run."""
    traj = _trajectory(db, run_id)
    scores = _scores_for(db, run_id)
    data = [[name, scores[name], traj[name]["trajectory"],
             traj[name]["movement"], traj[name]["delta"]]
            for name in sorted(scores, key=lambda n: -scores[n])]
    return _csv_response(data,
                         ["Company", "Current Score", "Trajectory", "Movement", "Delta"],
                         f"maya_run_{run_id}.csv")


@router.get("/api/runs/{run_id}/combined.csv")
def combined_csv(run_id: str, db: Session = Depends(get_db)) -> Response:
    """Hugo × Maya side by side for one run DATE: what Hugo scored AND how Maya
    reads its movement, one row per company — the 'diff' in a single file."""
    traj = _trajectory(db, run_id)
    snaps = sorted(_date_snapshots(db, run_id).values(),
                   key=lambda r: -(r.assessed_score or 0))
    data = [[r.company_name,
             r.assessed_score, r.coverage, "YES" if r.outreach_eligible else "no",
             traj.get(r.company_name, {}).get("trajectory", ""),
             traj.get(r.company_name, {}).get("movement", ""),
             traj.get(r.company_name, {}).get("delta", "")]
            for r in snaps]
    return _csv_response(
        data,
        ["Company", "Hugo — Score", "Hugo — Coverage", "Hugo — Eligible",
         "Maya — Trajectory", "Maya — Movement", "Maya — Delta"],
        f"hugo_x_maya_run_{run_id}.csv")


@router.post("/api/runs/{run_id}/export")
def export_to_folder(run_id: str, db: Session = Depends(get_db)) -> dict:
    """Collect this run's Hugo, Maya and combined CSVs into a local folder
    (data/agent_results/run_<date>_<id>/) — a ready-to-upload bundle. If the
    SharePoint library is later synced via OneDrive, point AGENT_RESULTS_DIR
    at that synced path and the export lands straight in SharePoint."""
    from pathlib import Path

    runs = _runs_ordered(db)
    run = next((r for r in runs if r["run_id"] == run_id), None)
    if run is None:
        return {"ok": False, "error": "run not found"}

    base = Path(os.environ.get("AGENT_RESULTS_DIR", "data/agent_results"))
    folder = base / f"run_{run['run_date'] or 'undated'}"
    folder.mkdir(parents=True, exist_ok=True)

    def _dump(resp: Response, name: str):
        (folder / name).write_bytes(resp.body)

    _dump(hugo_csv(run_id, db), "hugo_scores.csv")
    _dump(maya_csv(run_id, db), "maya_trajectory.csv")
    _dump(combined_csv(run_id, db), "hugo_x_maya_comparison.csv")
    (folder / "README.txt").write_text(
        f"TPDL engine run {run['run_date']} ({run_id})\n"
        f"{run['companies']} companies · {run['eligible']} outreach-eligible (score >= 8)\n\n"
        f"{_hugo_recap(db, run)}\n{_maya_recap(db, runs, run)}\n\n"
        f"Files: hugo_scores.csv (Hugo output) · maya_trajectory.csv (Maya read) "
        f"· hugo_x_maya_comparison.csv (both side by side).\n", encoding="utf-8")
    return {"ok": True, "folder": str(folder.resolve()), "files": 4}
