"""Step 0 — Load: pick the companies a run will process, from the dashboard DB.

Three selectors (composable with --min-score):
    top N        — best assessed_score first (re-score the known universe)
    lunch        — Switzerland + Spain radar (the 67-target Lunch Campaign pool)
    names        — explicit list, e.g. --names "Straumann Group; UCB"

Each company comes out with its DB identity (website/location/revenue),
its icp_flag, and its PREVIOUS intelligence summary as historical context —
so a new run knows what the last one concluded (Neotek's historical_context).

Imports of `app.*` stay lazy: the engine remains usable standalone
(--fixture / --company) without the dashboard installed.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LoadedCompany:
    name: str
    sector: str | None
    identity: dict


def _to_loaded(c) -> LoadedCompany:
    return LoadedCompany(
        name=c.name,
        sector=c.sector,
        identity={
            "website": c.website,
            "location": c.location,
            "revenue": c.revenue,
            "icp_flag": bool(c.icp_flag),
            # Previous run's narrative = this run's historical context.
            "historical_context": c.intelligence_summary,
            "tech_stack_summary": c.tech_stack_summary,
        },
    )


def load_top(n: int, min_score: float = 0.0) -> list[LoadedCompany]:
    from app.database import SessionLocal
    from app.models import Company

    with SessionLocal() as db:
        rows = (db.query(Company)
                .filter(Company.assessed_score >= min_score)
                .order_by(Company.assessed_score.desc())
                .limit(n).all())
        return [_to_loaded(c) for c in rows]


def load_lunch(min_score: float = 0.0) -> list[LoadedCompany]:
    """Lunch Campaign pool: companies located in Switzerland or Spain."""
    from app.database import SessionLocal
    from app.models import Company
    from app.tools.radars import detect_country

    with SessionLocal() as db:
        rows = (db.query(Company)
                .filter(Company.assessed_score >= min_score)
                .order_by(Company.assessed_score.desc()).all())
        return [_to_loaded(c) for c in rows
                if detect_country(c.location) in ("CH", "ES")]


def load_names(names: list[str]) -> list[LoadedCompany]:
    from app.database import SessionLocal
    from app.models import Company

    wanted = [n.strip() for n in names if n.strip()]
    out: list[LoadedCompany] = []
    with SessionLocal() as db:
        for name in wanted:
            c = db.get(Company, name)
            if c is not None:
                out.append(_to_loaded(c))
            else:  # unknown to the DB — still runnable, just without identity
                out.append(LoadedCompany(name=name, sector=None, identity={}))
    return out
