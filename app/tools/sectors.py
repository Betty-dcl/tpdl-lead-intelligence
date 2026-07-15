"""Sector segmentation for Julie's outreach.

Each sector gets a messaging angle + proof points. These are now POPULATED with
TPDL's real positioning (public site + anonymised engagements): pharma and
dermatology have dedicated angles; the other five inherit the honest cross-sector
value line. Still pending from Andrés: the specific client NUMBERS/results to
harden the proof points (see .claude/andres-session.md). The `_PLACEHOLDER`
sentinel + `is_defined()` remain so any future sector added blank is caught.
Keys match Company.sector_bucket (lowercased).
"""
from __future__ import annotations

_PLACEHOLDER = "[TO FILL — TPDL positioning for this sector]"

# Real TPDL positioning (public site + engagements, anonymised). Sector angles
# where TPDL has direct proof are specific; the rest inherit the cross-sector
# value line. Results still need Andrés's numbers (see .claude/andres-session.md).
_PROOF = [
    "Multi-market B2B loyalty programme for a global dermatology leader (interim → platform)",
    "Injectable drug launch delivered on Veeva/Salesforce with senior PMO",
    "350+ country web platforms harmonised; medical-education platform built",
]

# Cross-sector value — the firm's core, applies wherever there isn't a dedicated angle.
_GENERIC = {
    "angle": ("Bridge the gap between strategy and execution in Life Sciences: HCP / "
              "Sales-Rep / Patient journeys, behavioural-AI market intelligence & "
              "segmentation, global platform roll-outs & country enablement, and senior "
              "PMO / fractional teams. Swiss quality, hands-on delivery."),
    "proof_points": _PROOF,
}

SECTORS: dict[str, dict] = {
    "pharma": {
        "angle": ("For pharma commercial & medical teams: HCP segmentation and journey "
                  "mapping, global launch & country enablement, and medical-education / "
                  "loyalty / medical-affairs platforms — strategy turned into compliant "
                  "execution, with senior PMO to land it."),
        "proof_points": _PROOF,
    },
    "dermatology": {
        "angle": ("Deep dermatology track record: designed and rolled out a multi-market "
                  "B2B loyalty programme (interim-to-platform) and an integrated "
                  "medical-education platform for a global dermatology leader."),
        "proof_points": _PROOF,
    },
    # No dedicated proof yet in these — inherit the honest cross-sector value line.
    "medtech":      dict(_GENERIC),
    "dental":       dict(_GENERIC),
    "diagnostics":  dict(_GENERIC),
    "surgery":      dict(_GENERIC),
    "healthcare":   dict(_GENERIC),
}

_DEFAULT = dict(_GENERIC)


def get_sector_angle(sector_bucket: str | None) -> dict:
    if not sector_bucket:
        return _DEFAULT
    return SECTORS.get(sector_bucket.strip().lower(), _DEFAULT)


def is_defined(sector_bucket: str | None) -> bool:
    return get_sector_angle(sector_bucket)["angle"] != _PLACEHOLDER


def list_sectors() -> list[tuple[str, bool]]:
    """Return [(sector, is_defined)] for the configured sectors."""
    return [(name, cfg["angle"] != _PLACEHOLDER) for name, cfg in SECTORS.items()]
