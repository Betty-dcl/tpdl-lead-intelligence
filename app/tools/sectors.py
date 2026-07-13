"""Sector segmentation for Julie's outreach.

Each sector gets a messaging angle + proof points. These are PLACEHOLDERS —
TPDL fills them in with the real positioning per sector (the "content I'll give
you later"). Keys match Company.sector_bucket (lowercased).
"""
from __future__ import annotations

_PLACEHOLDER = "[TO FILL — TPDL positioning for this sector]"

SECTORS: dict[str, dict] = {
    "pharma":       {"angle": _PLACEHOLDER, "proof_points": []},
    "medtech":      {"angle": _PLACEHOLDER, "proof_points": []},
    "dental":       {"angle": _PLACEHOLDER, "proof_points": []},
    "diagnostics":  {"angle": _PLACEHOLDER, "proof_points": []},
    "dermatology":  {"angle": _PLACEHOLDER, "proof_points": []},
    "surgery":      {"angle": _PLACEHOLDER, "proof_points": []},
    "healthcare":   {"angle": _PLACEHOLDER, "proof_points": []},
}

_DEFAULT = {"angle": _PLACEHOLDER, "proof_points": []}


def get_sector_angle(sector_bucket: str | None) -> dict:
    if not sector_bucket:
        return _DEFAULT
    return SECTORS.get(sector_bucket.strip().lower(), _DEFAULT)


def is_defined(sector_bucket: str | None) -> bool:
    return get_sector_angle(sector_bucket)["angle"] != _PLACEHOLDER


def list_sectors() -> list[tuple[str, bool]]:
    """Return [(sector, is_defined)] for the configured sectors."""
    return [(name, cfg["angle"] != _PLACEHOLDER) for name, cfg in SECTORS.items()]
