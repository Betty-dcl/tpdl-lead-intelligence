"""Engine data contracts — the shapes that flow between the 6 steps.

The split lives HERE, structurally:
- `RawDoc`          → only the research + extraction steps ever hold one.
- `EvidenceBlock`   → the ONLY thing the interpreter is allowed to see.
- `InterpretedSignal` / `ScoredSignal` → interpretation output + deterministic math.
- `CompanyResult`   → maps 1:1 onto the 38-column scored_results.csv row.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

# The 6 scored signal categories (anything else is NOT a signal).
SIGNAL_CATEGORIES = (
    "leadership_change",
    "hiring",
    "ma_expansion",
    "pe_event",
    "digital_initiative",
    "org_restructuring",
)

# Signal → TPDL service areas (Neotek design, CLAUDE.md).
TPDL_SERVICE_AREAS: dict[str, str] = {
    "leadership_change": "Operating model / Commercial effectiveness",
    "hiring": "Commercial effectiveness / Digital execution & activation",
    "ma_expansion": "Operating model alignment / CRM & data strategy",
    "pe_event": "Operating model alignment",
    "digital_initiative": "Digital execution & activation / Customer journey optimisation",
    "org_restructuring": "Operating model alignment / CRM & data strategy",
}


@dataclass
class RawDoc:
    """One raw research document (article, job post, IR page…).

    NEVER passed to the interpreter — extraction-side only.
    """
    source: str                    # e.g. "serper_news", "exa_q1", "perplexity", "fixture"
    url: str | None                # None ⇒ unverifiable (Perplexity-style)
    title: str
    text: str
    published: date | None = None  # as reported by the source, if any


@dataclass
class EvidenceItem:
    """One verbatim sentence isolated by the extractor. No paraphrase, ever."""
    quote: str                     # MUST appear verbatim in its source doc
    source: str                    # source name (from RawDoc.source)
    url: str | None                # from RawDoc.url
    event_date: date | None        # date stated IN the quote/doc, else None
    category: str                  # one of SIGNAL_CATEGORIES


# Recap-mode categories (top 10-15 mega-cap trend-watch, pipeline/recap.py).
# Deliberately separate from SIGNAL_CATEGORIES — recap mode has no scoring
# step and explicitly WANTS product launches (excluded from the 6 above).
RECAP_CATEGORIES = ("new_product", "ma_activity", "tech_platform", "other")


@dataclass
class RecapItem:
    """One verbatim recap fact (mega-cap trend-watch). Same verbatim-lock
    discipline as EvidenceItem, but a distinct type on purpose: a recap item
    must never be able to flow into verbatim_qa()/score.interpret_and_score()
    through some future refactor (both take EvidenceItem/EvidenceBlock by
    type — a shared type would make that a silent bug instead of a hard
    type error)."""
    quote: str                     # MUST appear verbatim in its source doc
    source: str                    # source name (from RawDoc.source)
    url: str | None                # from RawDoc.url
    event_date: date | None        # date stated IN the quote/doc, else None
    category: str                  # one of RECAP_CATEGORIES


@dataclass
class EvidenceBlock:
    """Everything the interpreter is allowed to know about a company.

    Structurally excludes raw text: only isolated verbatim quotes.
    """
    company_name: str
    sector: str | None
    items: list[EvidenceItem] = field(default_factory=list)
    tech_stack_summary: str | None = None   # from step 1 (already a summary, not raw)

    def categories_found(self) -> list[str]:
        return sorted({i.category for i in self.items})


@dataclass
class InterpretedSignal:
    """The interpreter's judgement on ONE signal category.

    signal_strength is its ONLY scoring input (0-6). Everything else
    (recency, corroboration, total) is deterministic code, not the model.
    """
    category: str
    what_happened: str             # grounded in the quotes
    why_it_matters: str            # EVENT → PRESSURE → GAP → TPDL SERVICE AREA
    tpdl_relevance: str            # service area(s), or "" if chain incomplete
    confidence: str                # low | medium | high
    signal_strength: int           # 0-6 — SOLE model-set scoring input
    evidence: list[EvidenceItem] = field(default_factory=list)


@dataclass
class ScoredSignal:
    """InterpretedSignal + the deterministic arithmetic (code, not model)."""
    signal: InterpretedSignal
    recency_points: int            # 0-2
    corroboration_points: int      # 0-2
    total: float                   # strength + recency + corroboration (0-10)


@dataclass
class CompanyResult:
    """One company's full engine output → one scored_results.csv row."""
    name: str
    sector: str | None = None
    website: str | None = None
    location: str | None = None
    revenue: str | None = None

    intelligence_summary: str = ""             # EXACTLY 3 sentences
    signals: list[ScoredSignal] = field(default_factory=list)
    signals_not_evidenced: list[str] = field(default_factory=list)

    tech_stack_summary: str | None = None
    historical_context: str | None = None

    icp_flag: bool = False
    icp_flag_reason: str | None = None
    review_flag: bool = False
    review_flag_reason: str | None = None

    run_date: str = ""                          # ISO timestamp

    # ── deterministic derivations ───────────────────────────────────────
    @property
    def assessed_score(self) -> float:
        """Mean over FOUND signals only — never over the 6 types."""
        if not self.signals:
            return 0.0
        return round(sum(s.total for s in self.signals) / len(self.signals), 1)

    @property
    def coverage(self) -> str:
        n = len({s.signal.category for s in self.signals})
        return f"{n} of 6 signal types evidenced"

    def outreach_eligible(self, threshold: float) -> bool:
        return bool(self.signals) and self.assessed_score >= threshold

    def top3(self) -> list[ScoredSignal]:
        return sorted(self.signals, key=lambda s: s.total, reverse=True)[:3]
