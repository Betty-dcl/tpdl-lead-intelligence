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


# ─────────────────────────────────────────────────────────────────────────────
# Data helpers
# ─────────────────────────────────────────────────────────────────────────────

def _runs_ordered(db: Session) -> list[dict]:
    """One row per run, oldest → newest. Aggregated in Python to avoid SQLite
    boolean-SUM quirks; 'eligible' is counted as score ≥ 8 (the threshold's
    definition), self-consistent with the number shown everywhere else."""
    by_run: dict[str, list] = {}
    for r in db.query(RunSnapshot).all():
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
                                      {"active_page": "runs"})


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
        })
    return {"runs": cards, "count": len(cards)}


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
    runs = _runs_ordered(db)
    idx = next((i for i, r in enumerate(runs) if r["run_id"] == run_id), 0)
    cur = {r.company_name: (r.assessed_score or 0) for r in
           db.query(RunSnapshot).filter(RunSnapshot.import_run_id == run_id).all()}
    old = {}
    if idx > 0:
        old = {r.company_name: (r.assessed_score or 0) for r in
               db.query(RunSnapshot)
               .filter(RunSnapshot.import_run_id == runs[idx - 1]["run_id"]).all()}
    data = []
    for name, score in sorted(cur.items(), key=lambda kv: -kv[1]):
        if name in old:
            delta = score - old[name]
            traj = f"{old[name]}→{score}"
            move = "RISING" if delta > 0 else "FADING" if delta < 0 else "stable"
        else:
            delta, traj, move = "", f"{score} (new)", "NEW"
        data.append([name, score, traj, move,
                     f"{delta:+.1f}" if delta != "" else ""])
    return _csv_response(data,
                         ["Company", "Current Score", "Trajectory", "Movement", "Delta"],
                         f"maya_run_{run_id[:8]}.csv")
