"""Maya — Analyst (step 2 of the sales pipeline).

Maya takes Hugo's scored universe (the `companies` table) and the evidenced
`signals` table and turns raw research into a decision: the weekly Top 50/100,
the companies that recur week over week, and the recurring trends.

Slash commands (read the scored DB — no API key needed for the data; Claude
interprets):
  - /top [N?]      → ranked shortlist (default 50) of in-scope companies.
  - /trends        → dominant signal types + TPDL service areas this week.
  - /recurring     → companies appearing across multiple weekly runs.
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

        # ── /top [N?] ────────────────────────────────────────────────────
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
            if not rows:
                return {
                    "augmented_message": "The user ran `/top` but the scored universe is empty. Say so and suggest Hugo runs the pipeline.",
                    "action": "built_top_list",
                    "task_title": "Top list (empty)",
                }
            lines = [
                f"{i+1}. {c.name} — {c.assessed_score} · {c.coverage} · "
                f"{c.sector_bucket or '—'}{' · ELIGIBLE' if c.outreach_eligible else ''}"
                for i, c in enumerate(rows)
            ]
            eligible = sum(1 for c in rows if c.outreach_eligible)
            augmented = (
                f"The user ran `/top {n}`. Here is the ranked Top {len(rows)} from Hugo's "
                f"scored universe (in-scope only, highest assessed_score first; "
                f"{eligible} are Outreach Eligible):\n\n" + "\n".join(lines) +
                "\n\nPresent this as Maya's weekly shortlist: group by score band "
                "(8+ Eligible / 5-7 Monitor), call out the standouts and the dominant "
                "sectors, and flag the 3-5 to prioritise. This list hands to Inès for contacts."
            )
            return {
                "augmented_message": augmented,
                "action": "built_top_list",
                "task_title": f"Weekly Top {n}",
                "metadata": {"n": len(rows), "eligible": eligible},
            }

        # ── /trends ──────────────────────────────────────────────────────
        if low == "/trends" or low.startswith("/trends"):
            with SessionLocal() as db:
                by_cat = (
                    db.query(Signal.category, func.count(Signal.id))
                    .group_by(Signal.category)
                    .order_by(func.count(Signal.id).desc())
                    .all()
                )
                by_rel = (
                    db.query(Signal.tpdl_relevance, func.count(Signal.id))
                    .filter(Signal.tpdl_relevance.isnot(None))
                    .group_by(Signal.tpdl_relevance)
                    .order_by(func.count(Signal.id).desc())
                    .limit(8)
                    .all()
                )
                total = db.query(func.count(Signal.id)).scalar() or 0
            cat_str = "\n".join(f"  - {c or 'uncategorised'}: {n}" for c, n in by_cat)
            rel_str = "\n".join(f"  - {r}: {n}" for r, n in by_rel)
            augmented = (
                f"The user ran `/trends`. Across {total} evidenced signals in the current "
                f"run, the distribution is:\n\nBy signal type:\n{cat_str}\n\n"
                f"By TPDL service area (top):\n{rel_str}\n\n"
                f"As Maya, read the dominant trends of the week: which signal types and "
                f"service areas are surging, what that implies about where TPDL should "
                f"focus, and which one or two themes are worth a marketing angle (hand to Iris)."
            )
            return {
                "augmented_message": augmented,
                "action": "analysed_trends",
                "task_title": "Weekly trends",
                "metadata": {"signals": total},
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
                        "run so far, so week-over-week recurrence cannot be computed yet. "
                        "As Maya, explain this view tracks companies whose signals persist "
                        "or re-appear across weekly runs (a strong prioritisation cue), and "
                        "that it activates automatically from the second imported run."
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
                        f"As Maya, rank the persistent ones (recurrence = higher priority): "
                        f"risers are heating up (flag the top ones for Inès), faders are "
                        f"cooling (say whether to keep monitoring or deprioritise)."
                    )
                    meta = {"runs": runs, "recurring": len(recurring),
                            "risers": len(risers), "faders": len(faders)}
            return {
                "augmented_message": augmented,
                "action": "recurring_analysis",
                "task_title": "Recurring companies",
                "metadata": meta,
            }

        return None
