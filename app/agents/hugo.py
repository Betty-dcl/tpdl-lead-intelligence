"""Hugo — Deep Research & Scoring (operator of the TPDL Lead Intelligence Pipeline).

Hugo owns the scored company universe produced by the Lead Intelligence
Pipeline (9 research sources, incl. an opt-in social/video scan via
agent-reach's CLIs — `pipeline/social_research.py` — → Sonnet 5 verbatim
extraction → Opus 4.8 interpretation → scored CSV, ingested into the
`companies` table). The engine
is rebuilt in `pipeline/` and proven live (first real runs 2026-07-17); live
runs spend money and are launched deliberately from the CLI, never from chat.
The universe mixes vintages (May baseline + per-run refreshes) — every command
below surfaces the per-company run date so staleness is never silent.

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
from app.tools.signal_density import signal_categories

HUGO_ID: str = AgentID.HUGO.value

# Discovery output shown by /candidates (module-level so tests can repoint it).
from pathlib import Path as _Path
DISCOVERY_CSV = _Path("data/csv/discovery_candidates.csv")


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
    if not out:
        return "  (no evidenced signals)"
    cats = signal_categories(c)
    density = (f"  ⚡ {len(cats)} signals stacked ({' + '.join(cats)}) — higher conviction "
               f"than a single-signal company at an equal score.\n" if len(cats) >= 2 else "")
    return density + "\n".join(out)


class HugoAgent(BaseAgent):
    def _dispatch_command(self, user_message: str) -> Optional[dict]:
        text = user_message.strip()
        # Workspace "Generate brief" button sends `/generate <company>` —
        # Hugo's brief IS the full /company intelligence brief.
        if text.lower().startswith("/generate"):
            text = "/company" + text[len("/generate"):]
        low = text.lower()

        # ── /rerun — trigger / explain an engine run ─────────────────────
        if low == "/rerun" or low.startswith("/rerun"):
            from app.config import settings
            anthropic_ok = bool(settings.anthropic_api_key) and \
                settings.anthropic_api_key != "not-set"
            # A real refresh also needs at least one research source — an
            # Anthropic-only setup would extract/score over empty research.
            research_ok = any([
                getattr(settings, "exa_api_key", ""),
                getattr(settings, "perplexity_api_key", ""),
                getattr(settings, "serpapi_key", ""),
                getattr(settings, "serper_api_key", ""),
            ])
            live_ready = anthropic_ok and research_ok
            keys_state = ("Anthropic + research keys present"
                          if live_ready else
                          "ANTHROPIC_API_KEY missing" if not anthropic_ok
                          else "no research key (Exa/Perplexity/SerpAPI/Serper) present")
            augmented = (
                "The user ran `/rerun`. Explain how a pipeline run works now, honestly:\n"
                "- A **dry-run smoke test** (zero cost, the probe fixture) can be launched "
                "from the **Usage page** button or `python -m pipeline.runner --fixture "
                "pipeline/fixtures/probe_diagnostics.json`. It proves the chain "
                "(research → extract → score) but NEVER overwrites the scored database.\n"
                f"- A **live run** {'IS' if live_ready else 'is NOT'} currently possible "
                f"({keys_state}). Live runs spend real money and are launched from the "
                "CLI so the cost stays explicit and capped: `python -m pipeline.runner "
                "--top 5 --live --max-usd 1` (or `--lunch`, or `--batch --submit` + "
                "`--fetch` for machine-free volume runs), then `python import_csv.py "
                "<out.csv>` to feed the run into the database and Maya's /recurring. "
                "Cadence decision: ~one run per month.\n"
                "As Hugo, relay this plainly and NEVER claim you already refreshed the data."
            )
            return {
                "augmented_message": augmented,
                "action": "rerun_explained",
                "task_title": "/rerun",
                "metadata": {"live_ready": live_ready, "anthropic": anthropic_ok,
                             "research": research_ok},
            }

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
                latest = db.query(func.max(Company.run_date)).scalar()
            if not rows:
                return {
                    "augmented_message": (
                        f"The user ran `/scan{(' ' + sector) if sector else ''}` but no "
                        f"in-scope companies matched. Say so briefly and suggest `/stats`."
                    ),
                    "action": "scanned_universe",
                    "task_title": f"Scan — {sector or 'all'} (empty)",
                }
            latest_day = latest.date() if latest else None

            def _fresh(c) -> str:
                if not c.run_date:
                    return "run date unknown"
                day = c.run_date.date()
                return ("fresh (latest run)" if day == latest_day
                        else f"scored {day} — STALE")

            lines = [
                f"- {c.name} — score {c.assessed_score} · {c.coverage} · "
                f"{c.sector_bucket or '—'} · {c.location or '—'}"
                f"{' · OUTREACH ELIGIBLE' if c.outreach_eligible else ''} · {_fresh(c)}"
                for c in rows
            ]
            stale = sum(1 for c in rows if c.run_date and c.run_date.date() != latest_day)
            augmented = (
                f"The user ran `/scan{(' ' + sector) if sector else ''}`. Here are the "
                f"top {len(rows)} scored companies from my Lead Intelligence Pipeline "
                f"(highest assessed_score first; {stale} carry a STALE score from an "
                f"earlier run, not re-verified since):\n\n" + "\n".join(lines) +
                "\n\nPresent this as a tight prioritised shortlist. Call out which are "
                "Outreach Eligible (score ≥ 8) and recommend the 2-3 to act on first. "
                "Weigh freshness: a STALE high score means 'verify before acting'. "
                "Remind the user a high score with low coverage = one strong signal."
            )
            return {
                "augmented_message": augmented,
                "action": "scanned_universe",
                "task_title": f"Scan — {sector or 'all'}",
                "metadata": {"sector": sector, "returned": len(rows), "stale": stale},
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
            with SessionLocal() as db:
                latest = db.query(func.max(Company.run_date)).scalar()
            latest_day = latest.date() if latest else None
            if c.run_date:
                day = c.run_date.date()
                scored_line = (f"Scored on: {day} (latest run — fresh)"
                               if day == latest_day else
                               f"Scored on: {day} — STALE (not re-verified in the "
                               f"latest run of {latest_day})")
            else:
                scored_line = "Scored on: unknown run date"
            block = (
                f"COMPANY: {c.name}\n"
                f"Sector: {c.sector_bucket} ({c.sector or '—'}) · Location: {c.location or '—'} · "
                f"Revenue: {c.revenue or '—'} · Website: {c.website or '—'}\n"
                f"Assessed Score: {c.assessed_score} · Coverage: {c.coverage} · "
                f"Outreach Eligible: {c.outreach_eligible}\n"
                f"{scored_line}\n"
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
                f"(2) the strongest evidenced signal and its TPDL relevance — if the SIGNALS "
                f"block shows a ⚡ stacked-signals line, name it explicitly as higher conviction, "
                f"(3) a timing call — engage now / monitor / verify first — with why "
                f"(a STALE score argues for 'verify first'). "
                f"Then note this company is ready to hand to Maya for shortlisting."
            )
            return {
                "augmented_message": augmented,
                "action": "company_brief",
                "task_title": f"Intel brief — {c.name}",
                "metadata": {"company": c.name, "score": c.assessed_score},
            }

        # ── /candidates — discovery output, for human review BEFORE spending ─
        if low == "/candidates" or low.startswith("/candidates"):
            import csv as _csv
            path = DISCOVERY_CSV
            if not path.exists():
                return {
                    "augmented_message": (
                        "The user ran `/candidates` but no discovery output exists yet. "
                        "Explain: the discovery step (market watch over the 6 signal themes "
                        "+ the earnings-call angle) is launched from the CLI — "
                        "`python -m pipeline.runner --discover --live` (<$0.50) — and writes "
                        "data/csv/discovery_candidates.csv. Scoring candidates afterwards is "
                        "a separate, deliberate paid step (--names)."
                    ),
                    "action": "discovery_candidates",
                    "task_title": "/candidates (none yet)",
                }
            with open(path, encoding="utf-8", newline="") as f:
                rows = list(_csv.DictReader(f))
            by_theme: dict[str, list[str]] = {}
            for r in rows:
                by_theme.setdefault(r.get("Theme") or "unknown", []).append(
                    r.get("Company Name", "?"))
            listing = "\n".join(
                f"  [{theme}] ({len(names)}): " + ", ".join(names[:12])
                + (f" (+{len(names)-12} more)" if len(names) > 12 else "")
                for theme, names in sorted(by_theme.items(), key=lambda t: -len(t[1])))
            augmented = (
                f"The user ran `/candidates`. The last discovery pass found "
                f"{len(rows)} NEW companies (not in the scored universe), by watch "
                f"theme:\n\n{listing}\n\n"
                f"As Hugo, present this as the discovery shortlist AWAITING A HUMAN "
                f"DECISION: these names are found, not scored — scoring them costs "
                f"~$0.055/company (SERP quota: 2-3 searches each). Recommend which "
                f"themes to score first (earnings-call and PE are TPDL's strongest "
                f"entry points), and remind that the actual scoring run is launched "
                f"from the CLI, never from chat. Never invent details about these "
                f"companies — they have no evidence yet."
            )
            return {
                "augmented_message": augmented,
                "action": "discovery_candidates",
                "task_title": f"Discovery candidates ({len(rows)})",
                "metadata": {"candidates": len(rows), "themes": len(by_theme)},
            }

        # ── /stats ───────────────────────────────────────────────────────
        if low == "/stats" or low.startswith("/stats"):
            with SessionLocal() as db:
                total = db.query(func.count(Company.name)).scalar() or 0
                eligible = db.query(func.count(Company.name)).filter(
                    Company.outreach_eligible.is_(True)).scalar() or 0
                icp = db.query(func.count(Company.name)).filter(
                    Company.icp_flag.is_(True)).scalar() or 0
                review = db.query(func.count(Company.name)).filter(
                    Company.review_flag.is_(True)).scalar() or 0
                sectors = (
                    db.query(Company.sector_bucket, func.count(Company.name))
                    .group_by(Company.sector_bucket)
                    .order_by(func.count(Company.name).desc())
                    .all()
                )
                latest = db.query(func.max(Company.run_date)).scalar()
                fresh = 0
                if latest:
                    day_start = latest.replace(hour=0, minute=0, second=0, microsecond=0)
                    fresh = db.query(func.count(Company.name)).filter(
                        Company.run_date >= day_start).scalar() or 0
            sector_str = ", ".join(f"{(s or 'Unknown')}: {n}" for s, n in sectors)
            latest_day = latest.date() if latest else "unknown"
            augmented = (
                f"The user ran `/stats`. Here is my Lead Intelligence Pipeline universe "
                f"as currently scored in the database:\n\n"
                f"- Total companies: {total}\n"
                f"- Outreach Eligible (score ≥ 8): {eligible}\n"
                f"- ICP-flagged (out of target criteria): {icp}\n"
                f"- Review-flagged (needs a 60s human check): {review}\n"
                f"- Freshness: latest run {latest_day} refreshed {fresh} companies; "
                f"the other {total - fresh} carry scores from earlier runs (stale)\n"
                f"- By sector: {sector_str}\n\n"
                f"Summarise the state of the universe in a few lines — including how "
                f"much of it is fresh vs stale — and point the user to `/scan` for the "
                f"shortlist or `/company [name]` for a full brief."
            )
            return {
                "augmented_message": augmented,
                "action": "universe_stats",
                "task_title": "Universe stats",
                "metadata": {"total": total, "eligible": eligible,
                             "review": review, "fresh": fresh},
            }

        return None
