"""ICP targeting — deterministic, no network (unit-testable), mirrors radars.py.

The engine DISCOVERS broadly across European life sciences; this layer is the
TARGETING filter on top of it (decision Betty, 2026-07-22, "Market Intel July
2026" ICP brief formalised by Nathalie). It marks a company as OUT of the ICP
(`out_of_scope=True`) with a plain reason, so the UI/Maya can exclude it from
outreach without deleting the discovery.

Negative ICP (hard exclusions):
  1. Consulting / advisory / systems-integration firms   (e.g. Zühlke)
  2. CDMO / contract or pure manufacturing                (e.g. Lonza)
  3. Known revenue < €100M  — BUT private / undisclosed revenue is KEPT
     (mid-size Spanish players often don't publish; a floor set too high would
     cut dynamic growers like Leti Pharma at €200–300M).

Everything else stays in scope. The six confirmed campaign targets (Cantabria
Labs, Mediderma/Sesderma, Ferrer, ISDIN, Leti Pharma, Biologix) are never
excluded here.
"""
from __future__ import annotations

import re
import unicodedata

# The confirmed campaign targets — never excluded (safety net against a hint
# matching a real target's description).
CONFIRMED_TARGETS = {
    "cantabria labs", "mediderma", "sesderma", "ferrer", "isdin",
    "leti pharma", "letipharma", "biologix",
}

# Curated known out-of-ICP names (sector is often "Unknown" for these, so name
# is the reliable signal). Lowercased, accent-stripped, substring match.
_CONSULTING_NAMES = {
    "zuhlke", "accenture", "deloitte", "capgemini", "mckinsey", "bcg",
    "boston consulting", "kpmg", "ey ", "pwc", "cognizant", "infosys",
    "publicis", "cgi", "sopra steria", "atos", "wipro",
}
_CDMO_NAMES = {
    "lonza", "catalent", "recipharm", "siegfried", "patheon", "samsung biologics",
    "wuxi", "boehringer ingelheim biopharmaceuticals", "fareva", "delpharm",
}

# Keyword hints (matched on name + sector + sector_bucket text).
_CONSULTING_HINTS = (
    "consulting", "consultancy", "advisory", "systems integrator",
    "system integrator", "engineering services", "digital agency", "it services",
)
_CDMO_HINTS = (
    "cdmo", "contract manufacturing", "contract manufacturer",
    "contract development", "fill-finish", "fill finish", "api manufacturing",
    "contract research organization", " cro ",
)


def _norm(s: str | None) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower().strip()


def revenue_below_floor(revenue: str | None, floor_musd: float = 100.0) -> bool:
    """True only when we can CONFIDENTLY read a total revenue below the floor
    (in millions). Private / undisclosed / unparseable → False (keep it).

    Conservative: any 'billion'/'b+' reading, or a regional/partial qualifier,
    means we do NOT exclude on revenue."""
    low = _norm(revenue)
    if not low or low in {"na", "n/a", "none", "-", "unknown", "private", "undisclosed"}:
        return False
    if "billion" in low or re.search(r"\d\s*b\b|\d\s*b\+", low):
        return False                       # ≥ €1B, clearly above the floor
    # Partial/regional figures aren't the company's true size — don't exclude.
    if any(q in low for q in ("regional", "ops)", " ops", "local", "segment", "division")):
        return False
    # Collect magnitudes expressed in millions.
    millions = [float(n) for n in re.findall(r"(\d+(?:\.\d+)?)\s*m", low)]
    if not millions:
        return False                       # no clear million figure → keep
    # Use the TOP of any range as the company's size.
    return max(millions) < floor_musd


def assess_icp(name: str | None,
               sector: str | None = None,
               sector_bucket: str | None = None,
               revenue: str | None = None) -> dict:
    """Return {'out_of_scope': bool, 'reason': str|None}. `out_of_scope=True`
    maps to Company.icp_flag=True (ICP-flagged / not a target)."""
    n = _norm(name)
    if any(t in n for t in CONFIRMED_TARGETS):
        return {"out_of_scope": False, "reason": None}

    haystack = " ".join([n, _norm(sector), _norm(sector_bucket)])

    if any(k in n for k in _CONSULTING_NAMES) or any(h in haystack for h in _CONSULTING_HINTS):
        return {"out_of_scope": True, "reason": "consulting / advisory firm — out of ICP"}
    if any(k in n for k in _CDMO_NAMES) or any(h in haystack for h in _CDMO_HINTS):
        return {"out_of_scope": True, "reason": "CDMO / contract manufacturing — out of ICP"}
    if revenue_below_floor(revenue):
        return {"out_of_scope": True, "reason": "revenue below €100M floor"}

    return {"out_of_scope": False, "reason": None}
