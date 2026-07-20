"""Traceability — see every run, what Hugo produced and what Maya read of it,
with per-run CSV downloads and a plain-English recap. All data comes from
`RunSnapshot` (the append-only per-run history), so the page is honest about
what was actually stored, never reconstructed.
"""
from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse, Response
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

def _runs_ordered(db: Session) -> list[dict]:
    """One row per run, oldest → newest. Aggregated in Python to avoid SQLite
    boolean-SUM quirks; 'eligible' is counted as score ≥ 8 (the threshold's
    definition), self-consistent with the number shown everywhere else."""
    by_run: dict[str, list] = {}
    for r in db.query(RunSnapshot).all():
        if r.import_run_id == NEOTEK_REFERENCE_RUN:
            continue                       # exclude the external Neotek reference
        by_run.setdefault(r.import_run_id, []).append(r)
    out = []
    for run_id, rows in by_run.items():
        dates = [r.run_date for r in rows if r.run_date]
        out.append({
            "run_id": run_id,
            "companies": len(rows),
            "eligible": sum(1 for r in rows if (r.assessed_score or 0) >= 8),
            "top_score": max((r.assessed_score or 0) for r in rows) if rows else 0,
            "run_date": min(dates).date().isoformat() if dates else None,
        })
    out.sort(key=lambda x: x["run_date"] or "")
    return out


def _top_company(db: Session, run_id: str) -> tuple[str, float] | None:
    row = (db.query(RunSnapshot.company_name, RunSnapshot.assessed_score)
           .filter(RunSnapshot.import_run_id == run_id)
           .order_by(RunSnapshot.assessed_score.desc()).first())
    return (row.company_name, float(row.assessed_score or 0)) if row else None


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
    # companies present in BOTH runs, with score deltas
    cur = {r.company_name: r.assessed_score or 0 for r in
           db.query(RunSnapshot).filter(RunSnapshot.import_run_id == run["run_id"]).all()}
    old = {r.company_name: r.assessed_score or 0 for r in
           db.query(RunSnapshot).filter(RunSnapshot.import_run_id == prev["run_id"]).all()}
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

@router.get("/runs", response_class=HTMLResponse)
def runs_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "traceability.html",
                                      {"active_page": "runs",
                                       "sharepoint_url": SHAREPOINT_FOLDER_URL})


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

def _trajectory(db: Session, run_id: str) -> dict[str, dict]:
    """Per-company movement vs the previous TPDL-engine run (Neotek excluded)."""
    runs = _runs_ordered(db)
    idx = next((i for i, r in enumerate(runs) if r["run_id"] == run_id), 0)
    cur = {r.company_name: (r.assessed_score or 0) for r in
           db.query(RunSnapshot).filter(RunSnapshot.import_run_id == run_id).all()}
    old = {}
    if idx > 0:
        old = {r.company_name: (r.assessed_score or 0) for r in
               db.query(RunSnapshot)
               .filter(RunSnapshot.import_run_id == runs[idx - 1]["run_id"]).all()}
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
    """Hugo's output for one run: every company + its score, ranked."""
    rows = (db.query(RunSnapshot)
            .filter(RunSnapshot.import_run_id == run_id)
            .order_by(RunSnapshot.assessed_score.desc()).all())
    data = [[r.company_name, r.assessed_score, r.coverage,
             "YES" if r.outreach_eligible else "no", r.signals_found]
            for r in rows]
    return _csv_response(data,
                         ["Company", "Assessed Score", "Coverage",
                          "Outreach Eligible", "Signals Found"],
                         f"hugo_run_{run_id[:8]}.csv")


@router.get("/api/runs/{run_id}/maya.csv")
def maya_csv(run_id: str, db: Session = Depends(get_db)) -> Response:
    """Maya's read for one run: each company's trajectory vs the previous run."""
    traj = _trajectory(db, run_id)
    scores = {r.company_name: (r.assessed_score or 0) for r in
              db.query(RunSnapshot).filter(RunSnapshot.import_run_id == run_id).all()}
    data = [[name, scores[name], traj[name]["trajectory"],
             traj[name]["movement"], traj[name]["delta"]]
            for name in sorted(scores, key=lambda n: -scores[n])]
    return _csv_response(data,
                         ["Company", "Current Score", "Trajectory", "Movement", "Delta"],
                         f"maya_run_{run_id[:8]}.csv")


@router.get("/api/runs/{run_id}/combined.csv")
def combined_csv(run_id: str, db: Session = Depends(get_db)) -> Response:
    """Hugo × Maya side by side: what Hugo scored AND how Maya reads its movement,
    one row per company — the 'diff' between the two agents in a single file."""
    traj = _trajectory(db, run_id)
    rows = (db.query(RunSnapshot)
            .filter(RunSnapshot.import_run_id == run_id)
            .order_by(RunSnapshot.assessed_score.desc()).all())
    data = [[r.company_name,
             r.assessed_score, r.coverage, "YES" if r.outreach_eligible else "no",
             traj.get(r.company_name, {}).get("trajectory", ""),
             traj.get(r.company_name, {}).get("movement", ""),
             traj.get(r.company_name, {}).get("delta", "")]
            for r in rows]
    return _csv_response(
        data,
        ["Company", "Hugo — Score", "Hugo — Coverage", "Hugo — Eligible",
         "Maya — Trajectory", "Maya — Movement", "Maya — Delta"],
        f"hugo_x_maya_run_{run_id[:8]}.csv")


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
    folder = base / f"run_{run['run_date'] or 'undated'}_{run_id[:8]}"
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
