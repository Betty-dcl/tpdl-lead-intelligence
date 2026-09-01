"""Maya — Analyst (step 2 of the sales pipeline).

Hugo scores ONE company at a time (research → evidence → deterministic score) —
a point. Maya reads the whole scored PORTFOLIO, and reads it over TIME. That is
the division of labour: a scorer and a portfolio analyst are different jobs.

Maya answers three questions Hugo never touches:
  1. Of the hundreds Hugo scored, which handful do we act on this run, in what
     order, and why?          → /shortlist  (the deliverable handed to Inès)
  2. What is MOVING?           → /summary    (the run's executive read: top
     scores + why, biggest before/after movers, low-but-rising to watch)
  3. What is the SHAPE of the field? → /trends (dominant signal types + TPDL
     service areas → hands content themes to Iris)

She never re-scores and never researches — her only input is the scored
`companies` table + the `signals` and `run_snapshots` history.

Cadence: ~one engine run per MONTH for now — never imply weekly freshness.

Slash commands:
  - /shortlist          → the ACTIONABLE list for Inès (ACT NOW ≥8 · MONITOR 5-7).
  - /summary            → the run's executive summary (scores + movement + risers).
  - /trends             → dominant signal types + TPDL service areas (→ Iris).
  - /generate [company] → analyst positioning brief for ONE company (workspace button).
  - /top, /recurring    → DEPRECATED (folded into the Sales/Recurring pages +
                          /shortlist + /summary); they now redirect, don't duplicate.
"""
from typing import Optional

from sqlalchemy import func

from app.agents.base import BaseAgent
from app.config import AgentID
from app.database import SessionLocal
from app.models import Company, Signal
from app.tools.shortlist import shortlist_bands
from app.tools.signal_density import signal_categories as _signal_categories

MAYA_ID: str = AgentID.MAYA.value


def _run_movement(db) -> dict:
    """Cross-run trajectory of every company appearing in ≥2 runs.

    Trajectory is CHRONOLOGICAL (earliest run → latest run). A min→max display
    would invert every decline (a company falling 7.5→4.6 shown as a fake
    4.6→7.5 rise). Risers and faders are returned separately so a big decliner
    can never be pushed below a single capped 'hottest first' cut.
    """
    from datetime import datetime as _dt

    from app.models import RunSnapshot

    snaps = (db.query(RunSnapshot)
             .order_by(RunSnapshot.run_date, RunSnapshot.id).all())
    runs = len({s.import_run_id for s in snaps})
    if runs <= 1:
        return {"runs": runs, "recurring": 0, "risers": [], "faders": [],
                "stable": 0, "new": [], "not_rescanned": 0, "latest_score": {}}

    by_company: dict[str, list] = {}
    for s in snaps:
        by_company.setdefault(s.company_name, []).append(s)
    recurring = [
        (name, len({s.import_run_id for s in lst}),
         lst[0].assessed_score or 0, lst[-1].assessed_score or 0)
        for name, lst in by_company.items()
        if len({s.import_run_id for s in lst}) >= 2
    ]
    risers = sorted((t for t in recurring if t[3] > t[2]),
                    key=lambda t: -(t[3] - t[2]))[:20]
    faders = sorted((t for t in recurring if t[3] < t[2]),
                    key=lambda t: t[3] - t[2])[:20]
    stable = sum(1 for t in recurring if t[3] == t[2])

    def _run_key(rid):
        dates = [s.run_date for s in snaps if s.import_run_id == rid and s.run_date]
        return max(dates) if dates else _dt.min

    latest_run_id = max({s.import_run_id for s in snaps}, key=_run_key)
    new_names = sorted(
        (name for name, lst in by_company.items()
         if {s.import_run_id for s in lst} == {latest_run_id}),
        key=lambda name: -(by_company[name][-1].assessed_score or 0))
    not_rescanned = sum(
        1 for lst in by_company.values()
        if latest_run_id not in {s.import_run_id for s in lst})
    return {"runs": runs, "recurring": len(recurring), "risers": risers,
            "faders": faders, "stable": stable, "new": new_names,
            "not_rescanned": not_rescanned,
            "latest_score": {n: by_company[n][-1].assessed_score for n in new_names}}


def _fmt_trajectory(rows, arrow) -> str:
    return "\n".join(
        f"  - {name}: seen in {n} runs · {first}→{last} {arrow} ({last - first:+.1f})"
        for name, n, first, last in rows
    ) or "  (none)"


def _company_trajectory(db, name: str) -> str:
    """Maya's signature lens for ONE company: its CHRONOLOGICAL score path across
    runs, as a one-line movement read. A positioning brief should say whether the
    company is rising, falling or new — not just where it ranks today. Returns a
    ready-to-inject line (deterministic; collapses batches to one point per run)."""
    from app.models import RunSnapshot
    snaps = (db.query(RunSnapshot)
             .filter(RunSnapshot.company_name == name)
             .order_by(RunSnapshot.run_date, RunSnapshot.id).all())
    if not snaps:
        return "Movement: no run-history snapshot yet (activates from the second imported run)."
    per_run: dict = {}
    order: list = []
    for s in snaps:
        rid = s.import_run_id
        if rid not in per_run:
            per_run[rid] = {"date": s.run_date, "score": s.assessed_score or 0}
            order.append(rid)
        else:
            per_run[rid]["score"] = max(per_run[rid]["score"], s.assessed_score or 0)

    def _lbl(dt) -> str:
        return dt.date().isoformat() if dt else "?"

    path = [(per_run[r]["date"], per_run[r]["score"]) for r in order]
    if len(path) < 2:
        return (f"Movement: first appearance this run ({_lbl(path[0][0])} · "
                f"{path[0][1]}) — no prior history to compare.")
    first, last = path[0][1], path[-1][1]
    delta = last - first
    arrow = "↑ rising" if delta > 0 else "↓ falling" if delta < 0 else "→ flat"
    chain = " → ".join(f"{_lbl(d)} {sc}" for d, sc in path)
    return (f"Movement across {len(path)} runs: {chain}  ({arrow}, {delta:+.1f} since first "
            f"appearance) — Maya's key lens: {'heating up, prioritise' if delta > 0 else 'cooling, say whether to keep monitoring or deprioritise' if delta < 0 else 'stable'}.")


class MayaAgent(BaseAgent):
    def _dispatch_command(self, user_message: str) -> Optional[dict]:
        text = user_message.strip()
        low = text.lower()

        # ── /generate [company] — workspace brief: the analyst's read ────
        if low.startswith("/generate"):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                return {
                    "augmented_message": "The user ran `/generate` with no company. Ask which company they want the analyst positioning brief for.",
                    "action": "company_positioning",
                    "task_title": "/generate (no company)",
                }
            name = parts[1].strip()
            name_low = name.lower()
            with SessionLocal() as db:
                c = db.get(Company, name)
                if c is None:
                    for row in db.query(Company).all():
                        if row.name.lower() == name_low or name_low in row.name.lower():
                            c = row
                            break
                if c is None:
                    return {
                        "augmented_message": f"The user asked for a positioning brief on '{name}', not found in the scored universe. Suggest checking the name or running `/summary`.",
                        "action": "company_positioning",
                        "task_title": f"/generate: {name} (not found)",
                    }
                in_scope = (
                    db.query(func.count(Company.name))
                    .filter(Company.icp_flag.is_(False)).scalar() or 0
                )
                rank = (
                    db.query(func.count(Company.name))
                    .filter(Company.icp_flag.is_(False),
                            Company.assessed_score > c.assessed_score)
                    .scalar() or 0
                ) + 1
                sector_peers = (
                    db.query(func.count(Company.name))
                    .filter(Company.icp_flag.is_(False),
                            Company.sector_bucket == c.sector_bucket)
                    .scalar() or 0
                )
                sig_count = (
                    db.query(func.count(Signal.id))
                    .filter(Signal.company_name == c.name).scalar() or 0
                )
                trajectory = _company_trajectory(db, c.name)
            band = ("8+ Eligible" if c.assessed_score >= 8 else
                    "5-7 Monitor" if c.assessed_score >= 5 else
                    "1-4 Weak" if c.assessed_score >= 1 else "0 No signal")
            # rank/in_scope are computed over the in-scope set (icp_flag == False).
            # An icp-flagged company isn't part of that set, so a rank would be
            # incoherent — say it's out of scope instead.
            position_line = (
                "Scope: ICP-flagged — OUTSIDE the ranked in-scope set"
                if c.icp_flag else
                f"Rank: #{rank} of {in_scope} in-scope companies"
            )
            augmented = (
                f"The user ran `/generate {c.name}` — they want Maya's analyst positioning "
                f"brief for the workspace. Data from the scored universe:\n\n"
                f"COMPANY: {c.name} · {c.sector_bucket or '—'} · {c.location or '—'}\n"
                f"Score: {c.assessed_score} (band: {band}) · Coverage: {c.coverage or '—'} · "
                f"Outreach Eligible: {c.outreach_eligible}\n"
                f"{position_line}\n"
                f"Sector peers in scope ({c.sector_bucket or '—'}): {sector_peers}\n"
                f"Evidenced signals: {sig_count}\n"
                f"{trajectory}\n\n"
                f"As Maya, give the shortlist verdict in a few tight lines: where this company "
                f"sits in the current universe, its TRAJECTORY (rising/falling/new — your key "
                f"lens, weight it as heavily as the absolute score), whether to PRIORITISE / "
                f"MONITOR / DEPRIORITISE and why, and the next pipeline step (Inès for contacts "
                f"if prioritised). Reason only from the data above — never invent."
            )
            return {
                "augmented_message": augmented,
                "action": "company_positioning",
                "task_title": f"Positioning — {c.name}",
                "metadata": {"company": c.name, "rank": rank, "score": c.assessed_score},
            }

        # ── /shortlist — the ACTIONABLE list handed to Inès (threshold-banded) ─
        # Quality over a fixed count: a "top 50" pads the list with score-2
        # noise on a small run. The bar is score ≥ 8 (= outreach-eligible, the
        # constitution's threshold). 5-7 is a "monitor bench", <5 is parked.
        if low.startswith("/shortlist"):
            SOFT_CAP = 40    # only bites when the eligible band is unusually large
            with SessionLocal() as db:
                # Single source of truth (shared with Inès's batch hand-off):
                act, monitor = shortlist_bands(db)
                total = (db.query(Company)
                         .filter(Company.icp_flag.is_(False)).count())
                latest = db.query(func.max(Company.run_date)).scalar()
            if total == 0:
                return {
                    "augmented_message": "The user ran `/shortlist` but the scored universe is empty. Say so and suggest Hugo runs the pipeline.",
                    "action": "built_shortlist", "task_title": "Shortlist (empty)",
                }
            latest_day = latest.date() if latest else None

            def _line(c):
                fresh = ("fresh" if c.run_date and c.run_date.date() == latest_day
                         else f"STALE {c.run_date.date()}" if c.run_date else "no date")
                return (f"  - {c.name} — {c.assessed_score} · {c.coverage} · "
                        f"{c.sector_bucket or '—'} · {fresh}")

            capped = len(act) > SOFT_CAP
            act_shown = act[:SOFT_CAP]
            act_str = "\n".join(_line(c) for c in act_shown) or "  (none clear ≥8 this run)"
            mon_str = "\n".join(_line(c) for c in monitor[:20]) or "  (none)"
            augmented = (
                f"The user ran `/shortlist`. This is the ACTIONABLE list — quality-"
                f"gated by score, NOT a fixed count.\n\n"
                f"ACT NOW — outreach-eligible (score ≥ 8): {len(act)} companies"
                f"{f' (showing top {SOFT_CAP} by score→coverage→freshness)' if capped else ''}\n"
                f"{act_str}\n\n"
                f"MONITOR BENCH (5-7, not yet eligible — next-run candidates): "
                f"{len(monitor)}\n{mon_str}\n\n"
                f"As Maya: hand the ACT NOW band to Inès for contacts, weighing a STALE "
                f"high score as 'verify before acting'. Name the 3-5 strongest. Explain "
                f"the monitor bench is where next month's risers come from — don't push "
                f"them to outreach yet. If ACT NOW is empty, say so plainly: this run "
                f"produced nothing above the bar, which is an honest outcome, not a gap to fill."
            )
            return {
                "augmented_message": augmented,
                "action": "built_shortlist",
                "task_title": f"Shortlist — {len(act)} eligible",
                "metadata": {"eligible": len(act), "monitor": len(monitor), "capped": capped},
            }

        # ── /summary — the run's EXECUTIVE READ (Maya's flagship) ──────────
        # Nathalie's ask (§4b): lead with the top scores AND why they're valid,
        # spotlight the biggest before/after MOVERS, and flag low-but-rising
        # companies to start building contacts on early. This is the analyst
        # narrative — the Sales/Recurring pages hold the raw tables; Maya holds
        # the "so what". Absorbs what used to be split across /top + /recurring.
        if low.startswith("/summary") or low.startswith("/run"):
            with SessionLocal() as db:
                act, monitor = shortlist_bands(db)
                total = (db.query(Company)
                         .filter(Company.icp_flag.is_(False)).count())
                latest = db.query(func.max(Company.run_date)).scalar()
                flagged_act = sum(1 for c in act if c.review_flag)
                move = _run_movement(db)
            if total == 0:
                return {
                    "augmented_message": "The user ran `/summary` but the scored universe is empty. Say so and suggest Hugo runs the pipeline.",
                    "action": "run_summary", "task_title": "Run summary (empty)",
                }
            latest_day = latest.date() if latest else "?"

            def _why(c) -> str:
                cats = _signal_categories(c)
                sig = cats[0] if cats else "no lead signal"
                rel = f" → {c.s1_tpdl_relevance}" if c.s1_tpdl_relevance else ""
                flag = " ⚠REVIEW" if c.review_flag else ""
                density = (f" · {len(cats)} signals stacked ({' + '.join(cats)})"
                           if len(cats) >= 2 else "")
                return (f"  - {c.name} — {c.assessed_score} · {c.sector_bucket or '—'} · "
                        f"signal: {sig}{rel}{flag}{density}")

            top_act = "\n".join(_why(c) for c in act[:8]) or "  (none clear ≥8 this run)"

            # Signal-dense watchlist — companies with ≥2 corroborated signal
            # categories on the SAME company. External GTM benchmarks (Unify)
            # show reply rates roughly double at this density vs a single
            # signal at an equivalent score, so it deserves its own callout
            # rather than being buried in the per-line footnote above.
            dense = sorted(
                (c for c in (act + monitor) if len(_signal_categories(c)) >= 2),
                key=lambda c: (-len(_signal_categories(c)), -c.assessed_score),
            )[:8]
            dense_str = "\n".join(
                f"  - {c.name} — {c.assessed_score} · {' + '.join(_signal_categories(c))}"
                for c in dense
            ) or "  (none this run — no company has 2+ corroborated signal types)"

            # Movement section — chronological trajectory (risers/faders) + the
            # low-but-rising watch list (climbing but still under the 8 bar).
            if move["runs"] <= 1:
                movement_block = (
                    "MOVEMENT: only ONE run in history — before/after movement "
                    "activates from the second imported run."
                )
            else:
                watch = [t for t in move["risers"] if t[3] < 8][:8]
                watch_str = "\n".join(
                    f"  - {name}: {first}→{last} (+{last - first:.1f}) — still under 8, "
                    f"start building contacts early"
                    for name, n, first, last in watch) or "  (none)"
                new_str = "\n".join(
                    f"  - {name}: {move['latest_score'].get(name)}"
                    for name in move["new"][:10]) or "  (none)"
                movement_block = (
                    f"MOVEMENT across {move['runs']} runs "
                    f"({move['recurring']} companies seen in ≥2 runs):\n"
                    f"TOP RISERS (heating up):\n{_fmt_trajectory(move['risers'][:8], '↑')}\n"
                    f"TOP FADERS (cooling):\n{_fmt_trajectory(move['faders'][:8], '↓')}\n"
                    f"Stable: {move['stable']}. "
                    f"{move['not_rescanned']} historical companies were not re-scanned "
                    f"in the latest run (absence there = 'not scanned', not 'signal gone').\n"
                    f"LOW-BUT-RISING watch (climbing, still <8):\n{watch_str}\n"
                    f"NEW this run (first appearance ever):\n{new_str}"
                )

            augmented = (
                f"The user ran `/summary` — Maya's executive read of the latest run "
                f"({latest_day}). Data from the scored universe + run history:\n\n"
                f"HEADLINE: {len(act)} outreach-eligible (≥8) of {total} in-scope companies; "
                f"{len(monitor)} on the 5-7 monitor bench; {flagged_act} of the ACT NOW band "
                f"carry a ⚠ review flag (60-second human check before acting).\n\n"
                f"TOP SCORES (act-now band, strongest first) — with their lead signal:\n"
                f"{top_act}\n\n"
                f"SIGNAL-DENSE (2+ corroborated signal types on the same company — weigh "
                f"these as HIGHER conviction than a single-signal company at an equal or even "
                f"slightly higher score, not as a tie-breaker footnote):\n{dense_str}\n\n"
                f"{movement_block}\n\n"
                f"As Maya, write the RUN EXECUTIVE SUMMARY the way Nathalie asks: lead with "
                f"the top scores AND why they're interesting/valid (name the signal), then "
                f"spotlight the biggest before/after movers — a company that jumped from a "
                f"weak score to eligible is a headline, not a footnote. Call out the signal-"
                f"dense companies explicitly as the strongest conviction bets this run, even "
                f"if a single-signal company scores marginally higher. Call out the low-but-"
                f"rising names as 'worth monitoring / start building contacts now' even below "
                f"8: the movement itself is the signal. Keep review flags visible. Reason only "
                f"from the data above — never invent a number or a trajectory."
            )
            return {
                "augmented_message": augmented,
                "action": "run_summary",
                "task_title": f"Run summary — {len(act)} eligible",
                "metadata": {"eligible": len(act), "monitor": len(monitor),
                             "runs": move["runs"], "risers": len(move["risers"]),
                             "faders": len(move["faders"]), "new": len(move["new"]),
                             "signal_dense": len(dense)},
            }

        # ── /trends ──────────────────────────────────────────────────────
        if low.startswith("/trends"):
            with SessionLocal() as db:
                # The signals table mixes vintages (companies kept from older
                # runs still carry their old signals). Counting everything as
                # "the trends" lets the old stock drown the fresh run — segment
                # by the company's import run instead.
                latest_run = (
                    db.query(Company.import_run_id)
                    .filter(Company.run_date.isnot(None))
                    .order_by(Company.run_date.desc())
                    .limit(1).scalar()
                )
                latest_date = db.query(func.max(Company.run_date)).scalar()

                def _cat_dist(fresh: bool):
                    q = (db.query(Signal.category, func.count(Signal.id))
                         .join(Company, Signal.company_name == Company.name))
                    q = (q.filter(Company.import_run_id == latest_run) if fresh
                         else q.filter(Company.import_run_id != latest_run))
                    return q.group_by(Signal.category).order_by(
                        func.count(Signal.id).desc()).all()

                fresh_cat = _cat_dist(fresh=True)
                stock_cat = _cat_dist(fresh=False)
                fresh_companies = (db.query(func.count(Company.name))
                                   .filter(Company.import_run_id == latest_run)
                                   .scalar() or 0)
                stock_companies = (db.query(func.count(Company.name))
                                   .filter(Company.import_run_id != latest_run)
                                   .scalar() or 0)
                by_rel = (
                    db.query(Signal.tpdl_relevance, func.count(Signal.id))
                    .join(Company, Signal.company_name == Company.name)
                    .filter(Signal.tpdl_relevance.isnot(None),
                            Company.import_run_id == latest_run)
                    .group_by(Signal.tpdl_relevance)
                    .order_by(func.count(Signal.id).desc())
                    .limit(8)
                    .all()
                )
                total = db.query(func.count(Signal.id)).scalar() or 0

            def _fmt_dist(dist):
                return "\n".join(f"  - {c or 'uncategorised'}: {n}" for c, n in dist) or "  (none)"

            fresh_total = sum(n for _, n in fresh_cat)
            latest_day = latest_date.date() if latest_date else "?"
            augmented = (
                f"The user ran `/trends`. The universe holds {total} evidenced signals, "
                f"but they mix vintages — the trend read must come from the LATEST run, "
                f"with the older stock as context only.\n\n"
                f"LATEST RUN ({latest_day} · {fresh_companies} companies · {fresh_total} signals) "
                f"— by signal type:\n{_fmt_dist(fresh_cat)}\n\n"
                f"OLDER STOCK ({stock_companies} companies, not re-scanned since their "
                f"earlier run) — by signal type:\n{_fmt_dist(stock_cat)}\n\n"
                f"By TPDL service area (latest run only, top):\n"
                + ("\n".join(f"  - {r}: {n}" for r, n in by_rel) or "  (none)") +
                "\n\nAs Maya, read the dominant trends OF THE LATEST RUN: which signal "
                "types and service areas dominate the fresh data, how that differs from "
                "the older stock's mix, what it implies about where TPDL should focus, "
                "and which one or two themes are worth a marketing angle (hand to Iris)."
            )
            return {
                "augmented_message": augmented,
                "action": "analysed_trends",
                "task_title": "Run trends",
                "metadata": {"signals": total, "fresh_signals": fresh_total,
                             "fresh_companies": fresh_companies},
            }

        # ── /top, /recurring — DEPRECATED (folded into pages + /shortlist + /summary) ─
        # These duplicated UI pages. They no longer render a second copy of the
        # list; they point to the right surface so nobody hits a dead command.
        if low.startswith("/top"):
            return {
                "augmented_message": (
                    "The user ran `/top`. This scan view now lives on the Sales dashboard "
                    "(ranked, filterable, with per-run deltas). As Maya, say this in one or "
                    "two lines and point them to the real analyst outputs instead: "
                    "`/shortlist` for what to ACT ON now (Inès-ready), and `/summary` for the "
                    "run's executive read (top scores + who's moving). Do NOT reproduce a "
                    "ranked list here — that would just duplicate the Sales page."
                ),
                "action": "redirect",
                "task_title": "/top → Sales page + /shortlist",
            }
        if low.startswith("/recurring"):
            return {
                "augmented_message": (
                    "The user ran `/recurring`. Run-over-run movement now lives in two "
                    "places: the Recurring page (the full matrix of every company across "
                    "scans) and Maya's `/summary` (the executive read of who's rising/falling "
                    "and why). As Maya, point them there in a line or two — the risers/faders "
                    "narrative is part of `/summary` now. Do NOT reproduce the matrix here."
                ),
                "action": "redirect",
                "task_title": "/recurring → Recurring page + /summary",
            }

        return None
