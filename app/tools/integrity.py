"""Dataset-wide integrity checks — Vera's deterministic universe audit.

Every check codifies a REAL defect class found while auditing the first two
runs (2026-07): duplicate companies from the source CSV, legacy summaries that
break the 3-sentence constitution, missing locations (which disable the
Europe-first SERP locale), sentinel summaries left by scoring failures, and
cross-table drift. Pure functions over the DB — zero API calls, zero cost,
safe to run any time. Vera surfaces the result via `/audit` (no argument).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models import Company, Signal

# Kept deliberately tolerant: the constitution says exactly 3 sentences, but
# legitimate summaries sometimes split a clause on an abbreviation — 2-4 is the
# "clearly fine" band; outside it is worth a human glance, not an alarm.
_SENTENCE_BAND = (2, 4)

_NAME_NOISE = re.compile(
    r"\b(group|holding|ag|sa|sl|gmbh|inc|ltd|llc|europe|international)\b")


def _sentences(text: str | None) -> int:
    return len([s for s in re.split(r"(?<=[.!?])\s+", (text or "").strip()) if s])


def _norm_name(name: str) -> str:
    n = re.sub(r"\(.*?\)", "", name.lower())
    n = _NAME_NOISE.sub("", n)
    return re.sub(r"\W+", " ", n).strip()


@dataclass
class IntegrityReport:
    total: int = 0
    duplicate_groups: list[list[str]] = field(default_factory=list)
    bad_summaries: list[tuple[str, int]] = field(default_factory=list)   # (name, n_sentences)
    sentinel_summaries: list[str] = field(default_factory=list)
    eligibility_mismatch: list[str] = field(default_factory=list)
    unflagged_high_conf_no_url: list[str] = field(default_factory=list)
    missing_location: list[str] = field(default_factory=list)
    unknown_sector: int = 0
    signals_drift: tuple[int, int] | None = None   # (signals rows, s1-3 columns) if they differ

    @property
    def issue_count(self) -> int:
        return (len(self.duplicate_groups) + len(self.bad_summaries)
                + len(self.sentinel_summaries) + len(self.eligibility_mismatch)
                + len(self.unflagged_high_conf_no_url) + len(self.missing_location)
                + (1 if self.signals_drift else 0))

    def lines(self, cap: int = 8) -> str:
        """Human-readable findings block for the agent prompt."""
        out = []

        def sec(title, items, fmt=str):
            if not items:
                out.append(f"  ✓ {title}: none")
            else:
                shown = ", ".join(fmt(i) for i in items[:cap])
                more = f" (+{len(items) - cap} more)" if len(items) > cap else ""
                out.append(f"  ✗ {title} ({len(items)}): {shown}{more}")

        sec("Duplicate company groups", self.duplicate_groups, lambda g: " / ".join(g))
        sec("Summaries outside the 2-4 sentence band", self.bad_summaries,
            lambda t: f"{t[0]} ({t[1]}s)")
        sec("Sentinel/failed summaries", self.sentinel_summaries)
        sec("Score↔eligibility mismatches", self.eligibility_mismatch)
        sec("High-confidence signals without URL, NOT review-flagged",
            self.unflagged_high_conf_no_url)
        sec("Companies with no location (breaks the EU SERP locale)",
            self.missing_location)
        out.append(f"  {'✗' if self.signals_drift else '✓'} Signals-table sync: "
                   + (f"{self.signals_drift[0]} rows vs {self.signals_drift[1]} columns"
                      if self.signals_drift else "in sync"))
        out.append(f"  · Sector unknown (source data gap, informational): {self.unknown_sector}")
        return "\n".join(out)


def run_integrity_audit(db: Session) -> IntegrityReport:
    rows = db.query(Company).all()
    rep = IntegrityReport(total=len(rows))

    groups: dict[str, list[str]] = {}
    for c in rows:
        key = _norm_name(c.name)
        if key:
            groups.setdefault(key, []).append(c.name)
    rep.duplicate_groups = sorted(v for v in groups.values() if len(v) > 1)

    for c in rows:
        summary = c.intelligence_summary or ""
        if "No interpretation produced" in summary:
            rep.sentinel_summaries.append(c.name)
        elif summary.strip():
            n = _sentences(summary)
            if not (_SENTENCE_BAND[0] <= n <= _SENTENCE_BAND[1]):
                rep.bad_summaries.append((c.name, n))

        if (c.assessed_score >= 8) != bool(c.outreach_eligible):
            rep.eligibility_mismatch.append(c.name)

        if not c.review_flag:
            for i in (1, 2, 3):
                if (getattr(c, f"s{i}_confidence") == "high"
                        and not getattr(c, f"s{i}_urls")):
                    rep.unflagged_high_conf_no_url.append(c.name)
                    break

        if not (c.location or "").strip():
            rep.missing_location.append(c.name)
        if (c.sector_bucket or "") == "Unknown":
            rep.unknown_sector += 1

    n_signal_rows = db.query(Signal).count()
    n_cols = sum(1 for c in rows for i in (1, 2, 3) if getattr(c, f"s{i}_category"))
    if n_signal_rows != n_cols:
        rep.signals_drift = (n_signal_rows, n_cols)

    return rep
