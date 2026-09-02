"""Executive-move seniority/role classifier — chantier 4/4 (Slice 0), 2026-09-01
Nathalie meeting recap (.claude/state.md).

Pure functions, no DB/network (unit-testable), pattern copied from
`app/tools/segmentation.py` (token-based whole-word matching, most-specific-
first ordering) — but a DISTINCT taxonomy, deliberately not reused as-is:
segmentation.py solves TPDL's own commercial/data/digital outreach targeting,
where a small-company "General Manager" is treated as c_level-equivalent.
Here, Nathalie explicitly wants General Manager / Deputy General Manager kept
as their OWN tier (`minus_2`), separate from true C-suite — and a bare
"Manager" must NEVER match (that would dilute the filter she asked for, the
opposite of her intent: GM should be ELEVATED, not diluted).

`classify_seniority_tier` IS the ICP gate for this feature: a title outside
C-suite / -1 / -2 returns None and the move is discarded before persistence.
"""
from __future__ import annotations

import calendar
from datetime import date, datetime, timezone

from app.tools.segmentation import _norm  # generic string normalization, no domain coupling


def _has(norm: str, hints: tuple[str, ...]) -> bool:
    return any(f" {h} " in norm for h in hints)


# C-suite, UNAMBIGUOUS phrases: the 5 named roles from the meeting (CMO here =
# Chief Medical Officer, the standard pharma reading / COO/CIO/CTO/Chief
# Innovation Officer) + CEO-equivalent phrases that never collide with a VP
# title (Managing Director, and the ES/FR/DE "Director General" family — in
# those languages it IS the CEO, not a mid-level director). Checked FIRST.
_C_SUITE_HINTS = (
    "chief medical officer", "chief operating officer", "chief information officer",
    "chief technology officer", "chief innovation officer",
    "chief commercial officer", "chief executive officer", "chief digital officer",
    "cmo", "coo", "cio", "cto", "ceo", "cco",
    "managing director",
    # ES / FR / DE
    "director medico", "directora medica", "director de operaciones",
    "director de tecnologia", "director de innovacion", "directora de innovacion",
    "director general", "directora general", "gerente general",
    "directeur medical", "directeur des operations", "directeur technique",
    "directeur de l innovation", "directeur general", "directrice generale",
    "geschaftsfuhrer",
)

# -1: SVP/VP, explicitly. Checked BEFORE the generic "president" c-suite hint
# below — "Senior Vice President, Commercial" contains the bare-word
# substring " president ", which would otherwise wrongly fire the generic
# c-suite hint before this tier ever got a chance.
_MINUS_1_HINTS = (
    "senior vice president", "svp", "vice president", "vp",
    # ES / FR
    "vicepresidente senior", "vicepresidente",
    "vice-president senior", "vice-president",
)

# C-suite, GENERIC "president"-shaped phrase — checked AFTER minus_1 so it
# only fires on a true bare "President" (CEO-equivalent), never on "Vice
# President"/"Senior Vice President" (see _MINUS_1_HINTS comment above).
_C_SUITE_PRESIDENT_HINTS = ("president",)

# -2: Senior Director / General Manager / Deputy General Manager ONLY — a
# bare "director" or "manager" is NOT in this list on purpose (out of scope
# for this feature; segmentation.py's broader director/VP floor serves a
# different purpose). "general manager"/"gm"/"dgm" match the EXACT phrase or
# whole token, never a bare "manager" substring (Nathalie's own callout).
_MINUS_2_HINTS = (
    "senior director", "general manager", "deputy general manager", "gm", "dgm",
    # ES / FR
    "director general adjunto", "directora general adjunta", "director senior",
    "directeur general adjoint", "directrice generale adjointe", "directeur senior",
)


def classify_seniority_tier(title: str | None) -> str | None:
    """'c_level' | 'minus_1' | 'minus_2', or None (out of scope — the move is
    discarded before persistence, never stored)."""
    if not title:
        return None
    norm = _norm(title)
    if _has(norm, _C_SUITE_HINTS):
        return "c_level"
    if _has(norm, _MINUS_1_HINTS):
        return "minus_1"
    if _has(norm, _C_SUITE_PRESIDENT_HINTS):
        return "c_level"
    if _has(norm, _MINUS_2_HINTS):
        return "minus_2"
    return None


def is_in_scope(title: str | None) -> bool:
    """Convenience wrapper — the ICP-style gate used before persistence."""
    return classify_seniority_tier(title) is not None


# The 5 named roles from the meeting; anything else in-scope (VP/SVP/GM/Senior
# Director titles that aren't one of these 5) classifies as "other".
_ROLE_HINTS: dict[str, tuple[str, ...]] = {
    "cmo": ("chief medical officer", "cmo", "director medico", "directora medica", "directeur medical"),
    "coo": ("chief operating officer", "coo", "director de operaciones", "directeur des operations"),
    "cio": ("chief information officer", "cio", "director de tecnologia", "directeur informatique"),
    "cto": ("chief technology officer", "cto", "director tecnico", "directeur technique"),
    "chief_innovation": ("chief innovation officer", "director de innovacion",
                         "directora de innovacion", "directeur de l innovation"),
}


def classify_role_function(title: str | None) -> str | None:
    """'cmo'|'coo'|'cio'|'cto'|'chief_innovation'|'other', or None if no title."""
    if not title:
        return None
    norm = _norm(title)
    for role, hints in _ROLE_HINTS.items():
        if _has(norm, hints):
            return role
    return "other"


# ─────────────────────────────────────────────────────────────────────────────
# Follow-up timing — a field + a query, not a scheduler (see .claude/state.md,
# chantier 4 design). Nathalie's rationale: people start making strategic
# changes ~6 months into a new role, so following up just BEFORE that window
# (not after) is the useful moment.
# ─────────────────────────────────────────────────────────────────────────────

FOLLOW_UP_MONTHS = 4


def compute_follow_up_date(sent: date) -> date:
    """~4 calendar months after the connection was sent. Clamps to the last
    valid day of the target month (e.g. 31 Jan + 4 months → 31 May; 31 Dec
    + 4 months → 30 Apr)."""
    month_index = sent.month - 1 + FOLLOW_UP_MONTHS
    year = sent.year + month_index // 12
    month = month_index % 12 + 1
    day = min(sent.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


# ─────────────────────────────────────────────────────────────────────────────
# GDPR retention (decision Betty, 2026-09-02): this table stores named
# individuals' career history sourced from public press releases — more
# sensitive than the existing Contact table. Default policy: a `dismissed`
# move auto-purges after RETENTION_DAYS_DISMISSED days. To CONFIRM with
# Andrés/Nathalie before any live discovery run (not blocking — no live
# writer exists yet; pipeline/exec_moves.py is a later slice).
# ─────────────────────────────────────────────────────────────────────────────

RETENTION_DAYS_DISMISSED = 90


def purge_due(dismissed_at: datetime | date | None, today: date | None = None,
              retention_days: int = RETENTION_DAYS_DISMISSED) -> bool:
    """True if a dismissed move is past its retention window. Pure function —
    the actual delete query belongs to whichever code persists/reviews moves
    (not built yet)."""
    if dismissed_at is None:
        return False
    ref = dismissed_at.date() if isinstance(dismissed_at, datetime) else dismissed_at
    today = today or datetime.now(timezone.utc).date()
    return (today - ref).days >= retention_days
