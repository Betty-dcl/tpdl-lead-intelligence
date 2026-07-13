"""Inès's people-segmentation — pure functions, no DB, no network (unit-testable).

Three derivations from a contact's job title + the company's score:
  1. function  — commercial | data | digital  (which TPDL conversation they own)
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


def _norm(title: str) -> str:
    """Lowercase, punctuation→space, collapse, pad — so hints match whole tokens."""
    return " " + re.sub(r"[^a-z0-9]+", " ", title.lower()).strip() + " "


def _has(norm: str, hints: tuple[str, ...]) -> bool:
    return any(f" {h} " in norm for h in hints)


# Checked most-specific first: data, then digital, then commercial.
_DATA_HINTS = (
    "chief data", "data officer", "data", "analytics", "business intelligence",
    "bi", "data science", "head of data", "machine learning",
)
_DIGITAL_HINTS = (
    "chief digital", "digital officer", "digital", "chief technology", "cto",
    "chief information", "cio", "information officer", "technology officer",
    "transformation", "innovation", "it", "head of it", "e commerce", "ecommerce",
)
_COMMERCIAL_HINTS = (
    "commercial", "chief commercial", "cco", "sales", "revenue", "cro",
    "business development", "growth", "marketing", "cmo",
    "country manager", "general manager", "managing director", "chief executive",
    "ceo", "chief operating", "coo", "chief financial", "cfo",
)


def classify_function(title: str | None) -> str | None:
    """Map a job title to the TPDL function the person owns, or None if unclear."""
    if not title:
        return None
    norm = _norm(title)
    if _has(norm, _DATA_HINTS):
        return "data"
    if _has(norm, _DIGITAL_HINTS):
        return "digital"
    if _has(norm, _COMMERCIAL_HINTS):
        return "commercial"
    return None


# c_level phrases checked before 'director' so "Managing Director" → c_level, not director.
_C_LEVEL_HINTS = (
    "chief", "ceo", "cfo", "coo", "cto", "cio", "cdo", "cco", "cmo", "cro",
    "president", "founder", "owner", "managing director", "partner", "vorstand",
)
_VP_HINTS = ("vice president", "vp", "svp", "evp", "head of")
_DIRECTOR_HINTS = ("director", "directeur", "directora")


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
