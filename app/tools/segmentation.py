"""Inès's people-segmentation — pure functions, no DB, no network (unit-testable).

Three derivations from a contact's job title + the company's score:
  1. function  — commercial | data | digital | medical_affairs  (which TPDL conversation they own)
  2. seniority — c_level | vp | director | other
  3. crm_segment — 1 (warm) | 2 (active) | 3 (nurture)

Matching is token-based: the title is normalised to space-separated alphanumeric
tokens and each hint is matched whole-word. This is deliberate — a bare-substring
match wrongly fires "cto" inside "direCTOr". Write hints in normalised form
(lowercase, no punctuation/hyphens; multiword hints as space-joined words).

Rules mirror Inès's prompt (app/agents/prompts/ines.md):
  - function/seniority come from the real title ONLY — never inflate.
  - crm_segment is NEVER auto-set to 1: segment 1 ("excellent relationship") needs
    relationship evidence from the CRM, which this app doesn't have. We assign 2 or 3
    and leave 1 to human/CRM confirmation.
"""
from __future__ import annotations

import re
import unicodedata


def _norm(title: str) -> str:
    """Lowercase, fold accents, punctuation→space, collapse, pad — so hints match
    whole tokens. Accent-folding is deliberate: the campaign is Spain-focused, so
    'Médicos' / 'Análisis' / 'Président' must reduce to their ASCII hint form
    ('medicos' / 'analisis' / 'president') instead of being mangled by the
    alnum filter (which would otherwise drop the accented letter entirely)."""
    folded = unicodedata.normalize("NFKD", title.lower())
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    return " " + re.sub(r"[^a-z0-9]+", " ", folded).strip() + " "


def _has(norm: str, hints: tuple[str, ...]) -> bool:
    return any(f" {h} " in norm for h in hints)


# Checked most-specific first: medical affairs, then data, digital, commercial.
# Medical Affairs is a NAMED target family in Nathalie's ICP brief (§3b) and is
# routed to a SEPARATE sub-batch — so it must classify ahead of the others (a
# "Head of HCP Engagement" belongs to med-affairs, not "digital").
_MEDICAL_HINTS = (
    "medical affairs", "med affairs", "medical education", "med ed",
    "medical science liaison", "msl", "hcp engagement", "hcp",
    "medical director", "head of medical", "chief medical", "medical excellence",
    "scientific affairs",
    # ES / FR
    "asuntos medicos", "direccion medica", "director medico", "directora medica",
    "educacion medica", "enlace medico", "affaires medicales", "directeur medical",
    "responsable medical",
)
_DATA_HINTS = (
    "chief data", "data officer", "data", "analytics", "business intelligence",
    "bi", "data science", "head of data", "machine learning",
    # ES / FR
    "datos", "analitica", "ciencia de datos", "donnees", "analyse de donnees",
)
_DIGITAL_HINTS = (
    "chief digital", "digital officer", "digital", "chief technology", "cto",
    "chief information", "cio", "information officer", "technology officer",
    "transformation", "innovation", "it", "head of it", "e commerce", "ecommerce",
    # ES / FR
    "transformacion", "tecnologia", "informatica", "sistemas", "innovacion",
    "numerique", "digitale", "informatique",
)
_COMMERCIAL_HINTS = (
    "commercial", "chief commercial", "cco", "sales", "revenue", "cro",
    "business development", "growth", "marketing", "cmo",
    "country manager", "general manager", "managing director", "chief executive",
    "ceo", "chief operating", "coo", "chief financial", "cfo",
    # ES / FR — Spanish life-sciences titles are the campaign core
    "comercial", "ventas", "ventes", "mercadeo", "mercadotecnia",
    "director general", "directora general", "gerente general", "gerente comercial",
    "unidad de negocio", "president", "presidente", "presidenta", "directeur general",
)


def classify_function(title: str | None) -> str | None:
    """Map a job title to the TPDL function the person owns, or None if unclear."""
    if not title:
        return None
    norm = _norm(title)
    if _has(norm, _MEDICAL_HINTS):
        return "medical_affairs"
    if _has(norm, _DATA_HINTS):
        return "data"
    if _has(norm, _DIGITAL_HINTS):
        return "digital"
    if _has(norm, _COMMERCIAL_HINTS):
        return "commercial"
    return None


# c_level phrases checked before 'director' so "Managing Director" → c_level, not
# director. The multiword ES/FR heads ("director general", "gerente general") must
# live here too: in Spanish/French a "Director General" IS the CEO, not a mid-level
# director — matching them here (before _DIRECTOR_HINTS) prevents that demotion.
_C_LEVEL_HINTS = (
    "chief", "ceo", "cfo", "coo", "cto", "cio", "cdo", "cco", "cmo", "cro",
    "president", "founder", "owner", "managing director", "partner", "vorstand",
    # ES / FR / DE
    "director general", "directora general", "directeur general", "directrice generale",
    "general manager", "gerente general", "presidente", "presidenta",
    "geschaftsfuhrer", "pdg",
)
_VP_HINTS = ("vice president", "vp", "svp", "evp", "head of")
_DIRECTOR_HINTS = ("director", "directeur", "directora", "directrice")


def classify_seniority(title: str | None) -> str | None:
    """Map a job title to a seniority tier, or None if there is no title."""
    if not title:
        return None
    norm = _norm(title)
    if _has(norm, _C_LEVEL_HINTS):
        return "c_level"
    if _has(norm, _VP_HINTS):
        return "vp"
    if _has(norm, _DIRECTOR_HINTS):
        return "director"
    return "other"


# A "Senior Manager" sits below the Director+ floor, but Nathalie's brief (§3b)
# says at a SMALL company one can hold VP-equivalent scope — so flag rather than
# silently exclude. Inès surfaces the flag; the human decides.
_VP_EQUIVALENT_HINTS = ("senior manager", "sr manager", "senior lead", "gerente senior")


def flags_vp_equivalent(title: str | None) -> bool:
    """True if the title is below the Director floor but may be VP-equivalent at a
    small company (Senior Manager and the like) → flag for Nathalie's review."""
    if not title:
        return False
    norm = _norm(title)
    # Only borderline titles that DIDN'T already clear the floor.
    if classify_seniority(title) in ("c_level", "vp", "director"):
        return False
    return _has(norm, _VP_EQUIVALENT_HINTS)


_ACTIVE_SENIORITY = ("c_level", "vp", "director")


def initial_crm_segment(
    outreach_eligible: bool,
    function: str | None,
    seniority: str | None,
) -> int:
    """Initial CRM segment. Never returns 1 — segment 1 (warm relationship) needs
    CRM evidence this app doesn't hold, so it is left to human/CRM confirmation.

    2 (active follow-up) = good fit: outreach-eligible company + a recognised
    function + a senior decision-maker. Otherwise 3 (nurture / newsletter)."""
    if outreach_eligible and function and seniority in _ACTIVE_SENIORITY:
        return 2
    return 3
