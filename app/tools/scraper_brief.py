"""Inès's scraper-ready brief — the deliverable handed to Marketeering.ai.

Deterministic, no DB write, no network. Turns a scored Company into the
structured targeting brief Nathalie's ICP framework (ines.md §3b/§3c) asks for:

  1. the company-level radar read (country / lunch_campaign / language);
  2. the signal-driven priority roles (§3) layered over the 4 ICP functions (§3b);
  3. the per-company Sales Navigator config (titles · seniority floor · geo · keywords);
  4. the capture fields + flags (LinkedIn, tenure, recent-join);
  5. the WARM-FIRST tie-back checklist (§3c — partner-known / PipeDrive / 1st-degree);
  6. the Medical Affairs family held as a SEPARATE sub-batch for Nathalie.

This is what makes Mode A (no contact engine connected) genuinely useful: not
"I'd pull people later", but a brief the scraper/SDR can act on today. The one
thing it leaves blank is the actual names — those the scraper/engine fills.
NEVER invent a person here.
"""
from __future__ import annotations

from app.tools.apollo import titles_for_signal
from app.tools.radars import apply_radars

# The 4 ICP target functions (ines.md §3b), rendered as families so a brief is
# never C-suite-only. Medical Affairs is deliberately held OUT of this dict and
# rendered separately (MED_AFFAIRS_TITLES) — Nathalie reviews it as its own lot.
ICP_FUNCTION_TITLES: dict[str, tuple[str, ...]] = {
    "C-Suite": (
        "CEO", "COO", "CMO", "Chief Commercial Officer", "CIO", "Chief Digital Officer",
    ),
    "Commercial & Marketing": (
        "VP/Dir Commercial Operations", "VP/Dir Marketing", "Head of Omnichannel",
        "Head of Customer Engagement", "VP/Dir Sales Operations", "Head of Brand",
    ),
    "Digital & Technology": (
        "VP Digital Transformation", "Head of CRM", "Head of Digital Health",
        "Head of Commercial Data & Analytics", "IT Director (Commercial)",
    ),
}

# Held SEPARATE (§3b): routed to its own sub-batch for Nathalie's review, never
# mixed into the commercial list.
MED_AFFAIRS_TITLES: tuple[str, ...] = (
    "VP/Dir Medical Affairs", "Head of Medical Education",
    "VP/Dir MSL", "Head of HCP Engagement",
)

SENIORITY_FLOOR_LABEL = (
    "Director · VP · SVP · CVP · C-Level "
    "(a Senior Manager counts only if VP-equivalent at a small company → flag, don't drop)"
)

SALESNAV_KEYWORDS = (
    '"omnichannel"', '"HCP engagement"', '"digital transformation"',
    '"CRM"', '"commercial operations"',
)

# Per contact — what the scraper must capture. Recent-join drives the SDR rule
# that the acknowledge message never congratulates on a role unless a recent
# join (<3 months) is explicitly confirmed.
CAPTURE_FIELDS = (
    "full name", "title", "company", "LinkedIn URL", "tenure in role",
    "Spain-based vs regional HQ", "recent join (<3 months? yes/no)",
)


def salesnav_geography(country: str | None) -> str:
    """The Sales Navigator geography line for a company, from its radar country."""
    if country == "ES":
        return "Spain, expand to EMEA where a regional HQ exists"
    if country == "CH":
        return "Switzerland, expand to DACH / EMEA where a regional HQ exists"
    return "the company's HQ country, expand to EMEA where a regional HQ exists"


def tieback_checks(country: str | None) -> tuple[str, ...]:
    """The warm-first tie-back checklist (§3c) — raised on EVERY contact so the
    human/CRM resolves 'do we already know them?' before anyone is treated cold."""
    partner = (
        "Andrés or Pierre (Pierre is Barcelona-based → strong for the Spanish targets)"
        if country == "ES" else "Andrés or Pierre"
    )
    return (
        f"Partner connection — does {partner} already know this person? "
        "If yes → warm reconnect, NO duplicate outreach without sign-off.",
        "Existing CRM — already a contact in PipeDrive? "
        "If yes → Segment 1 candidate, reconnect subtly (not a fresh sequence).",
        "First-degree LinkedIn — a 1st-degree connection of the team? "
        "If yes → Segment 1 candidate, warm intro over cold.",
    )


def company_brief(c) -> dict:
    """Structured brief for one company (no names — those are the scraper's job)."""
    radar = apply_radars(None, c.location)
    return {
        "company": c.name,
        "sector": c.sector_bucket or "—",
        "location": c.location or "location unknown",
        "score": c.assessed_score,
        "lead_signal": c.s1_category or "none evidenced",
        "radar": radar,
        "priority_roles": list(titles_for_signal(c.s1_category)),
        "salesnav_geography": salesnav_geography(radar["country"]),
        "tieback": tieback_checks(radar["country"]),
    }


# ── Renderers — deterministic text blocks injected into Inès's augmented_message
#    so the LLM writes the final brief in-voice, but can never DROP §3b/§3c. ──

def _bullets(items) -> str:
    return "\n".join(f"  - {x}" for x in items)


def render_shared_config() -> str:
    """The parts of the brief identical across every company in a batch — the 4
    ICP families, the Med-Affairs separate sub-batch, seniority floor, keywords,
    capture fields, tie-back checklist. Rendered ONCE at the top of a batch."""
    families = "\n".join(
        f"  {fam}: {', '.join(titles)}" for fam, titles in ICP_FUNCTION_TITLES.items()
    )
    return (
        "SHARED SCRAPER CONFIG (applies to every company below)\n"
        "4 ICP target functions (layer over the signal-driven roles):\n"
        f"{families}\n"
        f"  ⚠️ Medical Affairs → SEPARATE SUB-BATCH for Nathalie (do not mix): "
        f"{', '.join(MED_AFFAIRS_TITLES)}\n"
        f"Seniority floor: {SENIORITY_FLOOR_LABEL}\n"
        f"Sales Nav keywords (optional): {' OR '.join(SALESNAV_KEYWORDS)}\n"
        f"Capture per contact: {', '.join(CAPTURE_FIELDS)}\n"
        "Tie-back check (§3c — run on EVERY contact before treating as cold):\n"
        f"{_bullets(tieback_checks(None))}\n"
        "No invented people — names are the scraper/engine's job."
    )


def render_company_brief(c) -> str:
    """Full scraper-ready brief for ONE company (Mode A `/contacts <company>`)."""
    b = company_brief(c)
    r = b["radar"]
    return (
        f"SCRAPER-READY BRIEF — {b['company']}\n"
        f"  {b['sector']} · {b['location']} · score {b['score']}\n"
        f"  Radar: country={r['country'] or 'other'} · "
        f"lunch_campaign={r['lunch_campaign']} · default language={r['language']}\n"
        f"  Lead signal: {b['lead_signal']} → PRIORITISE these roles first: "
        f"{', '.join(b['priority_roles'])}\n"
        f"  Then the 4 ICP functions:\n"
        + "\n".join(f"    {fam}: {', '.join(t)}" for fam, t in ICP_FUNCTION_TITLES.items())
        + f"\n    ⚠️ Medical Affairs → SEPARATE sub-batch for Nathalie: "
        f"{', '.join(MED_AFFAIRS_TITLES)}\n"
        f"  Sales Navigator config:\n"
        f"    - Company: search by name ({b['company']}), not a broad industry sweep\n"
        f"    - Seniority: {SENIORITY_FLOOR_LABEL}\n"
        f"    - Geography: {b['salesnav_geography']}\n"
        f"    - Keywords: {' OR '.join(SALESNAV_KEYWORDS)}\n"
        f"  Capture per contact: {', '.join(CAPTURE_FIELDS)}\n"
        f"  Tie-back check (§3c — every contact):\n{_bullets(b['tieback'])}"
    )


def render_batch_line(c) -> str:
    """Compact one-company line for the batch hand-off (`/contacts shortlist`).
    The shared config (render_shared_config) carries the ICP families / tie-back;
    here we vary only what differs per company: score, radar, signal→roles, geo."""
    b = company_brief(c)
    r = b["radar"]
    return (
        f"  - {b['company']} — score {b['score']} · {b['sector']} · {b['location']}\n"
        f"      radar: country={r['country'] or 'other'} lunch={r['lunch_campaign']} "
        f"lang={r['language']}\n"
        f"      signal {b['lead_signal']} → prioritise: {', '.join(b['priority_roles'])}\n"
        f"      Sales Nav geography: {b['salesnav_geography']}"
    )
