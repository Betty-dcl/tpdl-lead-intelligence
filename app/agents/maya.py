"""Maya — Analyst (step 2 of the sales pipeline).

Maya takes Hugo's scored universe (the `companies` table) and the evidenced
`signals` table and turns raw research into a decision: the current-run Top
50/100, the companies that recur run over run, and the run-level trends.
(Cadence: ~one engine run per month for now — never imply weekly freshness.)

Slash commands (read the scored DB — no API key needed for the data; Claude
interprets):
  - /shortlist     → the ACTIONABLE list handed to Inès: score-banded, not a
                     fixed count (ACT NOW ≥8 · MONITOR bench 5-7), soft-capped.
  - /top [N?]      → secondary SCAN view: the N best in-scope companies regardless.
  - /trends        → dominant signal types + TPDL service areas, latest run vs stock.
  - /recurring     → risers/faders/new across runs (needs ≥2 runs in history).
  - /generate [company] → analyst brief positioning one company in the universe
                          (used by the workspace "Generate brief" button).
"""
import re
from typing import Optional

from sqlalchemy import func

from app.agents.base import BaseAgent
from app.config import AgentID
from app.database import SessionLocal
from app.models import Company, Signal

MAYA_ID: str = AgentID.MAYA.value


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
                        "augmented_message": f"The user asked for a positioning brief on '{name}', not found in the scored universe. Suggest checking the name or running `/top`.",
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
                f"Evidenced signals: {sig_count}\n\n"
                f"As Maya, give the shortlist verdict in a few tight lines: where this company "
                f"sits in the current universe, whether to PRIORITISE / MONITOR / DEPRIORITISE "
                f"and why, and what the next pipeline step is (Inès for contacts if prioritised). "
                f"Reason only from the data above — never invent."
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
        if low == "/shortlist" or low.startswith("/shortlist"):
            SOFT_CAP = 40    # only bites when the eligible band is unusually large
            with SessionLocal() as db:
                rows = (db.query(Company)
                        .filter(Company.icp_flag.is_(False))
                        .order_by(Company.assessed_score.desc()).all())
                latest = db.query(func.max(Company.run_date)).scalar()
            if not rows:
                return {
                    "augmented_message": "The user ran `/shortlist` but the scored universe is empty. Say so and suggest Hugo runs the pipeline.",
                    "action": "built_shortlist", "task_title": "Shortlist (empty)",
                }
            latest_day = latest.date() if latest else None

            def _sig(c):   # tiebreakers: coverage depth, then freshness
                cov = int((c.coverage or "0")[0]) if (c.coverage or "")[:1].isdigit() else 0
                fresh = 1 if (c.run_date and c.run_date.date() == latest_day) else 0
                return (c.assessed_score, cov, fresh)

            def _line(c):
                fresh = ("fresh" if c.run_date and c.run_date.date() == latest_day
                         else f"STALE {c.run_date.date()}" if c.run_date else "no date")
                return (f"  - {c.name} — {c.assessed_score} · {c.coverage} · "
                        f"{c.sector_bucket or '—'} · {fresh}")

            act = sorted([c for c in rows if c.assessed_score >= 8], key=_sig, reverse=True)
            monitor = sorted([c for c in rows if 5 <= c.assessed_score < 8], key=_sig, reverse=True)
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

        # ── /top [N?] — a "give me the N best regardless" SCAN view (secondary) ─
        if low == "/top" or low.startswith("/top"):
            # Accept both "/top 5" and the glued "/top5" (the latter used to
            # silently fall through to the default 50).
            m = re.match(r"/top\s*(\d+)?", low)
            n = 50
            if m and m.group(1):
                n = max(5, min(100, int(m.group(1))))
            with SessionLocal() as db:
                rows = (
                    db.query(Company)
                    .filter(Company.icp_flag.is_(False))
                    .order_by(Company.assessed_score.desc())
                    .limit(n)
                    .all()
                )
                latest = db.query(func.max(Company.run_date)).scalar()
            if not rows:
                return {
                    "augmented_message": "The user ran `/top` but the scored universe is empty. Say so and suggest Hugo runs the pipeline.",
                    "action": "built_top_list",
                    "task_title": "Top list (empty)",
                }
            latest_day = latest.date() if latest else None

            def _freshness(c) -> str:
                # The universe mixes vintages: a company kept from an older run
                # carries a score that was never re-verified. Say so per line —
                # otherwise a stale May 9.0 silently outranks a fresh July 8.5.
                if not c.run_date:
                    return "run date unknown"
                day = c.run_date.date()
                return (f"scored {day} (latest run)" if day == latest_day
                        else f"scored {day} — STALE, not refreshed since")

            lines = [
                f"{i+1}. {c.name} — {c.assessed_score} · {c.coverage} · "
                f"{c.sector_bucket or '—'}{' · ELIGIBLE' if c.outreach_eligible else ''} "
                f"· {_freshness(c)}"
                for i, c in enumerate(rows)
            ]
            eligible = sum(1 for c in rows if c.outreach_eligible)
            stale = sum(1 for c in rows if c.run_date and c.run_date.date() != latest_day)
            augmented = (
                f"The user ran `/top {n}`. Here is the ranked Top {len(rows)} from Hugo's "
                f"scored universe (in-scope only, highest assessed_score first; "
                f"{eligible} are Outreach Eligible; {stale} of these scores are STALE — "
                f"from an earlier run, not re-verified in the latest one):\n\n"
                + "\n".join(lines) +
                "\n\nPresent this as Maya's current-run shortlist: group by score band "
                "(8+ Eligible / 5-7 Monitor), call out the standouts and the dominant "
                "sectors, and flag the 3-5 to prioritise. Weigh freshness explicitly: "
                "a fresh score is act-on-now; a STALE high score means 'verify before "
                "acting — signals may have moved'. This list hands to Inès for contacts."
            )
            return {
                "augmented_message": augmented,
                "action": "built_top_list",
                "task_title": f"Top {n} (current run)",
                "metadata": {"n": len(rows), "eligible": eligible, "stale": stale},
            }

        # ── /trends ──────────────────────────────────────────────────────
        if low == "/trends" or low.startswith("/trends"):
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

        # ── /recurring ───────────────────────────────────────────────────
        if low == "/recurring" or low.startswith("/recurring"):
            from app.models import RunSnapshot
            with SessionLocal() as db:
                runs = (db.query(func.count(func.distinct(RunSnapshot.import_run_id)))
                        .scalar() or 0)
                if runs <= 1:
                    augmented = (
                        "The user ran `/recurring`. The run-history table holds only ONE "
                        "run so far, so run-over-run recurrence cannot be computed yet. "
                        "As Maya, explain this view tracks companies whose signals persist "
                        "or re-appear across engine runs (~monthly cadence for now — a "
                        "strong prioritisation cue), and that it activates automatically "
                        "from the second imported run."
                    )
                    meta = {"runs": runs}
                else:
                    # Companies appearing in ≥2 runs, with their CHRONOLOGICAL
                    # score trajectory (first run → latest run). min→max would
                    # invert every decline: a company falling 7.5→4.6 would be
                    # displayed as "4.6→7.5 ↑ rising" — the exact opposite call.
                    snaps = (db.query(RunSnapshot)
                             .order_by(RunSnapshot.run_date, RunSnapshot.id).all())
                    by_company: dict[str, list] = {}
                    for s in snaps:
                        by_company.setdefault(s.company_name, []).append(s)
                    recurring = [
                        (name, len({s.import_run_id for s in lst}),
                         lst[0].assessed_score or 0, lst[-1].assessed_score or 0)
                        for name, lst in by_company.items()
                        if len({s.import_run_id for s in lst}) >= 2
                    ]
                    # Two explicit sections. A single "hottest latest score
                    # first" list capped at 40 would push every big DECLINER
                    # below the cut — Maya would never see the faders she is
                    # meant to call out.
                    risers = sorted((t for t in recurring if t[3] > t[2]),
                                    key=lambda t: -(t[3] - t[2]))[:20]
                    faders = sorted((t for t in recurring if t[3] < t[2]),
                                    key=lambda t: t[3] - t[2])[:20]
                    stable = len(recurring) - sum(1 for t in recurring if t[3] != t[2])

                    # New vs repeated (the dedup question): who shows up for the
                    # FIRST time in the latest run, and how much of the history
                    # was simply not re-scanned this time (runs may deliberately
                    # target a subset, so absence ≠ signal gone).
                    from datetime import datetime as _dt

                    def _run_key(rid):
                        dates = [s.run_date for s in snaps
                                 if s.import_run_id == rid and s.run_date]
                        return max(dates) if dates else _dt.min

                    latest_run_id = max({s.import_run_id for s in snaps}, key=_run_key)
                    new_names = sorted(
                        (name for name, lst in by_company.items()
                         if {s.import_run_id for s in lst} == {latest_run_id}),
                        key=lambda name: -(by_company[name][-1].assessed_score or 0))
                    not_rescanned = sum(
                        1 for lst in by_company.values()
                        if latest_run_id not in {s.import_run_id for s in lst})
                    new_str = "\n".join(
                        f"  - {name}: {by_company[name][-1].assessed_score}"
                        for name in new_names[:15]) or "  (none)"

                    def _fmt(rows_, arrow):
                        return "\n".join(
                            f"  - {name}: seen in {n} runs · score {first}→{last} "
                            f"{arrow} ({last - first:+.1f})"
                            for name, n, first, last in rows_
                        ) or "  (none)"

                    augmented = (
                        f"The user ran `/recurring`. Across {runs} runs in the history, "
                        f"{len(recurring)} companies persist (appear in ≥2 runs). Chronological "
                        f"score trajectory = earliest run → latest run.\n\n"
                        f"TOP RISERS (score climbing):\n{_fmt(risers, '↑')}\n\n"
                        f"TOP FADERS (score falling):\n{_fmt(faders, '↓')}\n\n"
                        f"Stable: {stable} companies with an unchanged score.\n\n"
                        f"NEW THIS RUN (first appearance ever, by score):\n{new_str}\n"
                        f"({len(new_names)} new in total; {not_rescanned} historical companies "
                        f"were not re-scanned in the latest run — absence there means 'not "
                        f"scanned', not 'signal gone'.)\n\n"
                        f"As Maya, rank the persistent ones (recurrence = higher priority): "
                        f"risers are heating up (flag the top ones for Inès), faders are "
                        f"cooling (say whether to keep monitoring or deprioritise), and call "
                        f"out the strongest NEW entrants — fresh blood is what widens the "
                        f"funnel."
                    )
                    meta = {"runs": runs, "recurring": len(recurring),
                            "risers": len(risers), "faders": len(faders),
                            "new": len(new_names)}
            return {
                "augmented_message": augmented,
                "action": "recurring_analysis",
                "task_title": "Recurring companies",
                "metadata": meta,
            }

        return None
