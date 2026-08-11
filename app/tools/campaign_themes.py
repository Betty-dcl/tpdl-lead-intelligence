"""The Market Intel July 2026 campaign themes — the marketing chain's shared spine.

Nathalie defined five priority content themes (brand-editorial.md §8, iris.md §6b)
so Andrés's LinkedIn content resonates with the ICP contacts once they connect.
They lived ONLY as prose inside two prompts — so Iris, Marc and Oliver each
restarted from a free-text topic and the "Iris → Marc → Oliver" pipeline was a
narrative, not a data flow.

Here they are structured data, so all three agents work from ONE definition (the
marketing analogue of app/tools/shortlist.py for Maya → Inès):
  - Iris surfaces + scores them (the standing campaign shortlist),
  - Marc grounds each piece in the RIGHT business principle + audience,
  - Oliver knows who the format is for.

Each theme names the TPDL business principle it proves (from the 10 in
brand-editorial.md §4) so content is never "about a technology" — the reframe
line carries the campaign's whole point: business problem, not IT problem.

Deterministic, no DB, no network — unit-testable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class CampaignTheme:
    key: str
    title: str
    audience: str
    business_principle: str   # which of TPDL's 10 principles this proves
    angle: str
    reframe: str              # the "business problem, not IT problem" pivot
    match_terms: tuple[str, ...]  # tokens that route a free-text theme here


CAMPAIGN_THEMES: tuple[CampaignTheme, ...] = (
    CampaignTheme(
        key="omnichannel-data",
        title="Omnichannel is a data problem, not a channel problem",
        audience="CMO / CCO drowning in channel decisions without the data architecture (esp. Ferrer, ISDIN)",
        business_principle="The Hidden Cost of Fragmentation",
        angle="each new channel added without one governed data foundation deepens fragmentation, not reach",
        reframe="the fix is a governed data architecture, not another channel",
        match_terms=("omnichannel", "channel", "data problem", "channels"),
    ),
    CampaignTheme(
        key="hcp-digital",
        title="HCP engagement in the digital age — what medical-education leaders need to own",
        audience="Medical Affairs / Med Ed leaders pulled into omnichannel decisions (an audience not yet saturated)",
        business_principle="The Enterprise Architecture Behind Commercial Excellence",
        angle="HCP engagement quality is an owned capability, not a set of campaigns — med-ed must own the architecture",
        reframe="engagement is an operating-model question, not a content-volume question",
        match_terms=("hcp", "medical education", "med ed", "engagement", "medical affairs"),
    ),
    CampaignTheme(
        key="spanish-scale",
        title="Building for global scale from a Spanish base",
        audience="Companies with international ambition from Spain (Cantabria, ISDIN, Ferrer)",
        business_principle="Standardisation Is Not About Control (standardisation creates freedom)",
        angle="a commercial architecture that travels — 80% standardised, 20% local — so scale doesn't cost local execution",
        reframe="going global is an operating-model design, not a market-by-market rebuild",
        match_terms=("global scale", "spanish", "spain", "international", "scale", "expansion"),
    ),
    CampaignTheme(
        key="architecture-brand",
        title="When you control the architecture, you control the brand",
        audience="C-suite — TPDL's canonical thought-leadership positioning, not a pitch",
        business_principle="Every Global Brand Is an Operating Model",
        angle="brand consistency is an outcome of governance, technology and operating model — not of campaigns",
        reframe="brand equity is built by the architecture beneath it, not by marketing output",
        match_terms=("architecture", "brand", "control", "governance"),
    ),
    CampaignTheme(
        key="midsize-transformation",
        title="Commercial transformation at mid-size life-sciences companies",
        audience="Mid-size life-sciences leaders — lean teams, multiple hats, limited IT, pressure to move fast",
        business_principle="Why Strategy Rarely Fails. Execution Does.",
        angle="mid-size constraints (lean teams, limited IT) make execution the real battleground big-pharma content ignores",
        reframe="the gap is execution capacity, not strategy or tooling",
        match_terms=("mid-size", "midsize", "mid size", "transformation", "lean", "commercial transformation"),
    ),
)

_BY_KEY = {t.key: t for t in CAMPAIGN_THEMES}


def _norm(text: str) -> str:
    return " " + re.sub(r"[^a-z0-9]+", " ", text.lower()).strip() + " "


def find_theme(text: str | None) -> CampaignTheme | None:
    """Route a free-text theme string to a campaign theme, or None.

    Matches on the theme key, then on any of the theme's match_terms appearing
    as a whole phrase in the text. First (most specific) match wins — the themes
    are ordered so the more distinctive ones are checked first."""
    if not text:
        return None
    norm = _norm(text)
    key_hit = text.strip().lower().replace(" ", "-")
    if key_hit in _BY_KEY:
        return _BY_KEY[key_hit]
    for theme in CAMPAIGN_THEMES:
        if theme.key in norm.replace(" ", "-"):
            return theme
        if any(f" {term} " in norm for term in theme.match_terms):
            return theme
    return None


def render_shortlist() -> str:
    """The standing campaign shortlist for Iris — the 5 themes, each with the
    business principle it proves and its audience. Rendered from code so Iris
    never drops or reorders Nathalie's brief."""
    lines = []
    for i, t in enumerate(CAMPAIGN_THEMES, 1):
        lines.append(
            f"  {i}. {t.title}\n"
            f"     proves: {t.business_principle} · for: {t.audience}\n"
            f"     reframe: {t.reframe}"
        )
    return "CAMPAIGN THEMES (Market Intel July 2026 · Nathalie's brief):\n" + "\n".join(lines)


def render_brief(theme: CampaignTheme) -> str:
    """The structured brief Marc gets when a theme routes to the campaign — so he
    grounds the piece in the RIGHT business principle instead of starting blind."""
    return (
        f"CAMPAIGN THEME MATCH — this theme is part of Nathalie's Market Intel campaign:\n"
        f"  Title: {theme.title}\n"
        f"  Business principle to PROVE (start here, not from a technology): {theme.business_principle}\n"
        f"  Target audience: {theme.audience}\n"
        f"  Canonical angle: {theme.angle}\n"
        f"  The reframe that IS the point (business problem, not IT problem): {theme.reframe}"
    )
