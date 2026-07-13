"""Hugo — Deep Research & Scoring (operator of the TPDL Lead Intelligence Pipeline).

Hugo owns the scored company universe produced by the Lead Intelligence
Pipeline (8 research sources → Haiku extraction → Sonnet scoring → scored CSV,
ingested into the `companies` table). He surfaces and explains that scored
output, and is the agent we'll wire the live re-run engines into once the API
keys (Exa, Perplexity, SerpAPI, Apify) are provided.

Slash commands (all read the already-scored `companies` table — no API key
needed to pull the data; Claude formats the response):
  - /scan [sector?]   → prioritised shortlist of outreach-eligible companies.
  - /company [name]    → full scored intelligence brief for one company.
  - /stats             → universe overview (counts, score bands, sectors).
  - /generate [name]   → alias of /company (used by the workspace "Generate brief" button).
"""
from typing import Optional

from sqlalchemy import func

from app.agents.base import BaseAgent
from app.config import AgentID
from app.database import SessionLocal
from app.models import Company

HUGO_ID: str = AgentID.HUGO.value


def _find_company(name: str) -> Optional[Company]:
    name_low = name.strip().lower()
    if not name_low:
        return None
    with SessionLocal() as db:
        exact = db.get(Company, name)
        if exact:
            return exact
        rows = db.query(Company).all()
        for c in rows:
            if c.name.lower() == name_low:
                return c
        for c in rows:
            if name_low in c.name.lower():
                return c
    return None


def _signal_lines(c: Company) -> str:
    out = []
    for i in (1, 2, 3):
        cat = getattr(c, f"s{i}_category")
        if not cat:
            continue
        urls = getattr(c, f"s{i}_urls") or getattr(c, f"s{i}_sources") or "no source"
        out.append(
            f"  Signal {i} — {cat} (confidence: {getattr(c, f's{i}_confidence')})\n"
            f"    What happened: {getattr(c, f's{i}_what_happened')}\n"
            f"    Why it matters: {getattr(c, f's{i}_why_it_matters')}\n"
            f"    TPDL relevance: {getattr(c, f's{i}_tpdl_relevance')}\n"
            f"    Sources: {urls}"
        )
    return "\n".join(out) if out else "  (no evidenced signals)"


class HugoAgent(BaseAgent):
    def _dispatch_command(self, user_message: str) -> Optional[dict]:
        text = user_message.strip()
        # Workspace "Generate brief" button sends `/generate <company>` —
        # Hugo's brief IS the full /company intelligence brief.
        if text.lower().startswith("/generate"):
            text = "/company" + text[len("/generate"):]
        low = text.lower()

        # ── /scan [sector?] ──────────────────────────────────────────────
        if low == "/scan" or low.startswith("/scan "):
            parts = text.split(maxsplit=1)
            sector = parts[1].strip() if len(parts) > 1 else None
            with SessionLocal() as db:
                q = db.query(Company).filter(Company.icp_flag.is_(False))
                if sector:
                    q = q.filter(
                        func.lower(Company.sector_bucket) == sector.lower()
                    )
                rows = q.order_by(Company.assessed_score.desc()).limit(15).all()
            if not rows:
                return {
                    "augmented_message": (
                        f"The user ran `/scan{(' ' + sector) if sector else ''}` but no "
                        f"in-scope companies matched. Say so briefly and suggest `/stats`."
                    ),
                    "action": "scanned_universe",
                    "task_title": f"Scan — {sector or 'all'} (empty)",
                }
            lines = [
                f"- {c.name} — score {c.assessed_score} · {c.coverage} · "
                f"{c.sector_bucket or '—'} · {c.location or '—'}"
                f"{' · OUTREACH ELIGIBLE' if c.outreach_eligible else ''}"
                for c in rows
            ]
            augmented = (
                f"The user ran `/scan{(' ' + sector) if sector else ''}`. Here are the "
                f"top {len(rows)} scored companies from my Lead Intelligence Pipeline "
                f"(highest assessed_score first):\n\n" + "\n".join(lines) +
                "\n\nPresent this as a tight prioritised shortlist. Call out which are "
                "Outreach Eligible (score ≥ 8) and recommend the 2-3 to act on first. "
                "Remind the user a high score with low coverage = one strong signal."
            )
            return {
                "augmented_message": augmented,
                "action": "scanned_universe",
                "task_title": f"Scan — {sector or 'all'}",
                "metadata": {"sector": sector, "returned": len(rows)},
            }

        # ── /company [name] ──────────────────────────────────────────────
        if low.startswith("/company"):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                return {
                    "augmented_message": (
                        "The user ran `/company` with no name. Ask which company from "
                        "the scored universe they want the full intelligence brief for."
                    ),
                    "action": "company_brief",
                    "task_title": "/company (no name)",
                }
            name = parts[1].strip()
            c = _find_company(name)
            if c is None:
                return {
                    "augmented_message": (
                        f"The user asked for '{name}', not found in the scored universe. "
                        f"Suggest checking spelling or running `/scan`."
                    ),
                    "action": "company_brief",
                    "task_title": f"/company: {name} (not found)",
                }
            block = (
                f"COMPANY: {c.name}\n"
                f"Sector: {c.sector_bucket} ({c.sector or '—'}) · Location: {c.location or '—'} · "
                f"Revenue: {c.revenue or '—'} · Website: {c.website or '—'}\n"
                f"Assessed Score: {c.assessed_score} · Coverage: {c.coverage} · "
                f"Outreach Eligible: {c.outreach_eligible}\n"
                f"ICP-flagged: {c.icp_flag} · Review-flagged: {c.review_flag}"
                f"{(' (' + c.review_flag_reason + ')') if c.review_flag and c.review_flag_reason else ''}\n\n"
                f"INTELLIGENCE SUMMARY:\n{c.intelligence_summary}\n\n"
                f"SIGNALS:\n{_signal_lines(c)}\n\n"
                f"TECH STACK: {c.tech_stack_summary or 'no data'}\n"
                f"HISTORICAL CONTEXT: {c.historical_context or '—'}"
            )
            augmented = (
                f"The user ran `/company {c.name}`. Present the full scored intelligence "
                f"brief from my pipeline using the data block below — reason ONLY from it, "
                f"never invent dates/sources/events.\n\n{block}\n\n"
                f"Give: (1) a 2-3 sentence read of where the commercial opening is, "
                f"(2) the strongest evidenced signal and its TPDL relevance, "
                f"(3) a timing call — engage now / monitor / verify first — with why. "
                f"Then note this company is ready to hand to Maya for shortlisting."
            )
            return {
                "augmented_message": augmented,
                "action": "company_brief",
                "task_title": f"Intel brief — {c.name}",
                "metadata": {"company": c.name, "score": c.assessed_score},
            }

        # ── /stats ───────────────────────────────────────────────────────
        if low == "/stats" or low.startswith("/stats"):
            with SessionLocal() as db:
                total = db.query(func.count(Company.name)).scalar() or 0
                eligible = db.query(func.count(Company.name)).filter(
                    Company.outreach_eligible.is_(True)).scalar() or 0
                icp = db.query(func.count(Company.name)).filter(
                    Company.icp_flag.is_(True)).scalar() or 0
                sectors = (
                    db.query(Company.sector_bucket, func.count(Company.name))
                    .group_by(Company.sector_bucket)
                    .order_by(func.count(Company.name).desc())
                    .all()
                )
            sector_str = ", ".join(f"{(s or 'Unknown')}: {n}" for s, n in sectors)
            augmented = (
                f"The user ran `/stats`. Here is my Lead Intelligence Pipeline universe "
                f"as currently scored in the database:\n\n"
                f"- Total companies: {total}\n"
                f"- Outreach Eligible (score ≥ 8): {eligible}\n"
                f"- ICP-flagged (out of target criteria): {icp}\n"
                f"- By sector: {sector_str}\n\n"
                f"Summarise the state of the universe in a few lines and point the user to "
                f"`/scan` for the shortlist or `/company [name]` for a full brief."
            )
            return {
                "augmented_message": augmented,
                "action": "universe_stats",
                "task_title": "Universe stats",
                "metadata": {"total": total, "eligible": eligible},
            }

        return None
