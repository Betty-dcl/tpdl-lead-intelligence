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
  4. Known revenue above the mega-cap ceiling (~$20B, configurable via
     scoring_config.yaml's `icp_ceiling_musd`, e.g. Pfizer/Sanofi/Merck) — these
     route to the separate "top 10-15 mega-cap" trend-watch instead of being
     scored (client request, Nathalie, 2026-09-01). Same conservative logic as
     the floor: unknown/private revenue is never excluded.

Everything else stays in scope. The six confirmed campaign targets (Cantabria
Labs, Mediderma/Sesderma, Ferrer, ISDIN, Leti Pharma, Biologix) are never
excluded here.
"""
from __future__ import annotations

import re
import unicodedata

from app.tools.radars import geo_region

# Geography is a PRIORITY signal, NOT an exclusion (Betty, 2026-07-22 pm): the core
# market is Switzerland / Spain / Middle East / rest of Europe, but she wants
# everything from the rest of the world too — nothing is geo-excluded. Use
# market_tier() below for prioritisation; icp_flag is driven only by company TYPE
# (consulting/CDMO/CRO/tools/distributor) and the <€100M revenue floor.
_CORE_MARKET_GEOS = {"CH", "ES", "Middle East", "Europe"}


def market_tier(location: str | None) -> str:
    """'core' (CH/ES/Middle East/Europe = TPDL's market, prioritise) or 'world'
    (everything else — still in scope, just lower priority). Never excludes."""
    return "core" if geo_region(location) in _CORE_MARKET_GEOS else "world"

# The confirmed campaign targets — never excluded (safety net against a hint
# matching a real target's description).
CONFIRMED_TARGETS = {
    "cantabria labs", "mediderma", "sesderma", "ferrer", "isdin",
    "leti pharma", "letipharma", "biologix",
}

# Curated known out-of-ICP names (sector is often "Unknown" for these, so name
# is the reliable signal). Lowercased, accent-stripped, substring match.
# Distinctive tokens only — no ultra-short substrings ("ey" would match
# "journey"/"Berkeley", "cgi" any word, etc.), which caused false positives.
_CONSULTING_NAMES = {
    "zuhlke", "accenture", "deloitte", "capgemini", "mckinsey",
    "boston consulting", "cognizant", "infosys", "sopra steria", "wipro",
    "productlife",
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


# Curated known NON-brand-owners (Nathalie's rule: TPDL targets brand owners
# that make their own commercial decisions — not CDMO/CRO/manufacturing,
# tools/instruments/reagents suppliers, distributors/pharmacies, or consultancies).
# Normalised substring → reason. Reviewed against the July discovery batch; extend
# as new off-profile names surface. Real targets (Recordati, Lundbeck, UCB,
# Galapagos, Chiesi, Pierre Fabre, ALK-Abelló, Almirall, ADVANZ…) are NOT here.
_KNOWN_OFF_ICP: tuple[tuple[str, str], ...] = (
    # CDMO / CRO / contract R&D & manufacturing services
    ("evotec", "CDMO/CRO — out of ICP"),
    ("eurofins", "testing/lab services (CRO) — out of ICP"),
    ("propharma", "pharma services/CRO — out of ICP"),
    ("exmoor", "CDMO — out of ICP"),
    ("veranova", "CDMO (API) — out of ICP"),
    ("avid bioservices", "CDMO — out of ICP"),
    ("kbi biopharma", "CDMO — out of ICP"),
    ("syngene", "CRO/CDMO — out of ICP"),
    ("solara active pharma", "API manufacturer (CDMO) — out of ICP"),
    ("cenexi", "CDMO — out of ICP"),
    ("sterling pharma", "CDMO (API) — out of ICP"),
    ("curida", "CDMO — out of ICP"),
    ("single use support", "manufacturing equipment/services — out of ICP"),
    ("atec pharmatechnik", "pharma equipment/manufacturing — out of ICP"),
    ("clinilabs", "CRO — out of ICP"),
    ("signant health", "clinical-trial tech/CRO — out of ICP"),
    ("tcg lifesciences", "CRO — out of ICP"),
    ("immunoprecise", "antibody CRO — out of ICP"),
    ("fairjourney", "antibody discovery CRO — out of ICP"),
    ("frontier scientific", "chemicals supplier — out of ICP"),
    ("capricorn scientific", "reagents supplier — out of ICP"),
    ("axol bioscience", "cell-products supplier — out of ICP"),
    # Tools / instruments / reagents suppliers (not brand owners)
    ("milliporesigma", "life-science tools/reagents supplier — out of ICP"),
    ("danaher", "tools/instruments conglomerate — out of ICP"),
    ("waters", "analytical instruments (tools) — out of ICP"),
    ("quanterix", "life-science tools/instruments — out of ICP"),
    ("akoya", "life-science tools/instruments — out of ICP"),
    ("berkeley lights", "life-science tools/instruments — out of ICP"),
    ("tmrw life sciences", "life-science tools/instruments — out of ICP"),
    ("epredia", "pathology instruments (tools) — out of ICP"),
    ("microm microtech", "lab instruments — out of ICP"),
    ("solmetex", "dental equipment/consumables — out of ICP"),
    ("atcc", "biological-materials supplier — out of ICP"),
    ("west pharmaceutical", "packaging/components supplier — out of ICP"),
    # Distributors / pharmacies / retail / parallel-import (not brand owners)
    ("docmorris", "online pharmacy/distribution — out of ICP"),
    ("redcare pharmacy", "online pharmacy/distribution — out of ICP"),
    ("walgreens", "pharmacy retail/distribution — out of ICP"),
    ("lloydspharmacy", "pharmacy retail — out of ICP"),
    ("orifarm", "parallel importer/distribution — out of ICP"),
    ("sciensus", "pharma homecare/services — out of ICP"),
    ("swixx biopharma", "market-access/distribution partner — out of ICP"),
    # Consulting / staffing
    ("pharmarelations", "pharma consulting/staffing — out of ICP"),
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


# Mega-cap ceiling default (M$) — overridable via scoring_config.yaml's
# `icp_ceiling_musd` (see pipeline/config.py::EngineConfig). Companies above
# this route to the separate "top 10-15 mega-cap" trend-watch, not scoring.
DEFAULT_ICP_CEILING_MUSD = 20000.0
MEGA_CAP_REASON = "revenue above $20B — mega-cap, out of ICP scope (watch-list candidate)"


def _revenue_musd_max(low: str) -> float | None:
    """Max magnitude (in millions) found in an already-normalized revenue
    string, reading both million (`\\d+m`) and billion (`\\d+b`) figures.
    None if nothing parseable — caller must treat that as 'unknown, keep'."""
    millions = [float(n) for n in re.findall(r"(\d+(?:\.\d+)?)\s*m", low)]
    billions = [float(n) * 1000 for n in re.findall(r"(\d+(?:\.\d+)?)\s*b(?:illion)?", low)]
    magnitudes = millions + billions
    return max(magnitudes) if magnitudes else None


def revenue_above_ceiling(revenue: str | None, ceiling_musd: float = DEFAULT_ICP_CEILING_MUSD) -> bool:
    """True only when we can CONFIDENTLY read a total revenue above the
    ceiling (in millions). Private / undisclosed / unparseable → False (keep
    it) — same conservative philosophy as revenue_below_floor()."""
    low = _norm(revenue)
    if not low or low in {"na", "n/a", "none", "-", "unknown", "private", "undisclosed"}:
        return False
    # Partial/regional figures aren't the company's true size — don't exclude.
    if any(q in low for q in ("regional", "ops)", " ops", "local", "segment", "division")):
        return False
    top = _revenue_musd_max(low)
    if top is None:
        return False                       # no clear figure → keep
    return top > ceiling_musd


def assess_icp(name: str | None,
               sector: str | None = None,
               sector_bucket: str | None = None,
               revenue: str | None = None,
               location: str | None = None,
               icp_ceiling_musd: float = DEFAULT_ICP_CEILING_MUSD) -> dict:
    """Return {'out_of_scope': bool, 'reason': str|None}. `out_of_scope=True`
    maps to Company.icp_flag=True (ICP-flagged / not a target)."""
    n = _norm(name)
    if any(t in n for t in CONFIRMED_TARGETS):
        return {"out_of_scope": False, "reason": None}

    for token, reason in _KNOWN_OFF_ICP:
        if token in n:
            return {"out_of_scope": True, "reason": reason}

    haystack = " ".join([n, _norm(sector), _norm(sector_bucket)])

    if any(k in n for k in _CONSULTING_NAMES) or any(h in haystack for h in _CONSULTING_HINTS):
        return {"out_of_scope": True, "reason": "consulting / advisory firm — out of ICP"}
    if any(k in n for k in _CDMO_NAMES) or any(h in haystack for h in _CDMO_HINTS):
        return {"out_of_scope": True, "reason": "CDMO / contract manufacturing — out of ICP"}
    if revenue_below_floor(revenue):
        return {"out_of_scope": True, "reason": "revenue below €100M floor"}
    if revenue_above_ceiling(revenue, icp_ceiling_musd):
        return {"out_of_scope": True, "reason": MEGA_CAP_REASON}

    # NB: geography never excludes — see market_tier() for prioritisation.
    return {"out_of_scope": False, "reason": None}
