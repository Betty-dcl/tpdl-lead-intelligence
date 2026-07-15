"""Step 4 — Interpretation & scoring (Opus 4.8) + deterministic arithmetic.

Structural isolation: every function here takes an `EvidenceBlock` — the type
system makes it impossible to hand the interpreter a RawDoc. The payload sent
to Opus is built exclusively from isolated verbatim quotes.

The model sets `signal_strength` (0-6) and NOTHING else. Recency, corroboration
and the total are pure code, driven by scoring_config.yaml.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import date
from urllib.parse import urlsplit

from pipeline.config import PROMPTS_DIR, EngineConfig, require_live
from pipeline.types import (
    SIGNAL_CATEGORIES,
    TPDL_SERVICE_AREAS,
    EvidenceBlock,
    EvidenceItem,
    InterpretedSignal,
    ScoredSignal,
)

logger = logging.getLogger(__name__)

SCORE_PROMPT = (PROMPTS_DIR / "score_opus.md").read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# Deterministic arithmetic (code, never the model)
# ─────────────────────────────────────────────────────────────────────────────

def recency_points(cfg: EngineConfig, event_date: date | None,
                   today: date | None = None) -> int:
    """≤90 days ⇒ full · ≤6 months ⇒ partial · undated ⇒ zero."""
    if event_date is None:
        return int(cfg.recency["no_date"])
    today = today or date.today()
    days = (today - event_date).days
    if days < 0:  # future-dated claims earn nothing
        return int(cfg.recency["no_date"])
    if days <= 90:
        return int(cfg.recency["within_90_days"])
    if days <= 182:
        return int(cfg.recency["within_6_months"])
    return 0


def _domain(url: str) -> str:
    """news.example.com/a and news.example.com/b are ONE source."""
    host = urlsplit(url).netloc.lower()
    return host.removeprefix("www.")


def corroboration_points(cfg: EngineConfig, evidence: list[EvidenceItem]) -> int:
    """Anchors = distinct URL *domains* (two links on one site ≠ two sources).

    - 0 anchors (e.g. Perplexity-only)          ⇒ 0 — corroborates but never anchors
    - 2+ anchors, or 1 anchor + a no-URL
      corroborator (Perplexity confirming it)   ⇒ 2
    - 1 anchor alone                            ⇒ 1
    """
    anchors = {_domain(e.url) for e in evidence if e.url}
    unanchored_corroborators = {e.source for e in evidence if not e.url}
    if not anchors:
        return int(cfg.corroboration["single_unverified"])
    if len(anchors) >= 2 or unanchored_corroborators:
        return int(cfg.corroboration["multiple_sources"])
    return int(cfg.corroboration["single_verified"])


def score_signal(cfg: EngineConfig, signal: InterpretedSignal,
                 today: date | None = None) -> ScoredSignal:
    """score = signal_strength (0-6) + recency (0-2) + corroboration (0-2)."""
    strength = max(0, min(6, int(signal.signal_strength)))  # clamp — rule 7
    best_date = max((e.event_date for e in signal.evidence if e.event_date),
                    default=None)
    rec = recency_points(cfg, best_date, today)
    cor = corroboration_points(cfg, signal.evidence)
    return ScoredSignal(
        signal=signal,
        recency_points=rec,
        corroboration_points=cor,
        total=float(strength + rec + cor),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Evidence payload — built ONLY from the block (structural isolation)
# ─────────────────────────────────────────────────────────────────────────────

def evidence_payload(block: EvidenceBlock) -> str:
    lines = [f"COMPANY: {block.company_name}",
             f"SECTOR: {block.sector or 'unknown'}"]
    if block.tech_stack_summary:
        lines.append(f"TECH STACK SUMMARY: {block.tech_stack_summary}")
    lines.append("\nEVIDENCE (verbatim quotes — the only facts that exist):")
    for i, e in enumerate(block.items, 1):
        lines.append(
            f"[{i}] category={e.category} source={e.source} "
            f"url={e.url or 'NONE'} date={e.event_date or 'NONE'}\n"
            f'    "{e.quote}"'
        )
    if not block.items:
        lines.append("(no evidence found)")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Live interpretation (Opus 4.8) — behind the money gate
# ─────────────────────────────────────────────────────────────────────────────

def live_interpret(cfg: EngineConfig, block: EvidenceBlock) -> tuple[list[InterpretedSignal], list[str], str]:
    require_live(cfg, cfg.anthropic_api_key, "Interpretation (Opus 4.8)")
    import anthropic

    client = anthropic.Anthropic(api_key=cfg.anthropic_api_key)
    response = client.messages.create(
        model=cfg.interpretation_model,
        max_tokens=4096,
        system=SCORE_PROMPT,
        messages=[{"role": "user", "content": evidence_payload(block)}],
    )
    text = "".join(b.text for b in response.content if b.type == "text")
    return _parse_interpretation(text, block)


def _parse_interpretation(text: str, block: EvidenceBlock) -> tuple[list[InterpretedSignal], list[str], str]:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return [], list(SIGNAL_CATEGORIES), "No interpretation produced. " * 3
    payload = json.loads(m.group())
    by_cat: dict[str, list[EvidenceItem]] = {}
    for e in block.items:
        by_cat.setdefault(e.category, []).append(e)

    signals = []
    for raw in payload.get("signals", []):
        cat = raw.get("category", "")
        if cat not in by_cat:   # rule 4: no evidence ⇒ not a signal, period.
            continue
        signals.append(InterpretedSignal(
            category=cat,
            what_happened=raw.get("what_happened", ""),
            why_it_matters=raw.get("why_it_matters", ""),
            tpdl_relevance=raw.get("tpdl_relevance") or "",
            confidence=raw.get("confidence", "low"),
            signal_strength=int(raw.get("signal_strength", 0)),
            evidence=by_cat[cat],
        ))
    not_evidenced = [c for c in SIGNAL_CATEGORIES
                     if c not in {s.category for s in signals}]
    summary = payload.get("intelligence_summary", "")
    return signals, not_evidenced, summary


# ─────────────────────────────────────────────────────────────────────────────
# Dry-run interpretation — deterministic, zero API
# ─────────────────────────────────────────────────────────────────────────────

_MOCK_STRENGTH = {  # standard-case defaults per category (dry-run only)
    "pe_event": 5, "leadership_change": 4, "ma_expansion": 4,
    "org_restructuring": 4, "digital_initiative": 3, "hiring": 3,
}


def mock_interpret(block: EvidenceBlock) -> tuple[list[InterpretedSignal], list[str], str]:
    """Deterministic stand-in for Opus 4.8 — same contract, zero cost."""
    by_cat: dict[str, list[EvidenceItem]] = {}
    for e in block.items:
        by_cat.setdefault(e.category, []).append(e)

    signals = []
    for cat, evidence in by_cat.items():
        area = TPDL_SERVICE_AREAS[cat]
        signals.append(InterpretedSignal(
            category=cat,
            what_happened=f"Evidence of {cat.replace('_', ' ')}: {evidence[0].quote[:160]}",
            why_it_matters=(f"{cat.replace('_', ' ').capitalize()} creates execution "
                            f"pressure and a capability gap aligned with {area}."),
            tpdl_relevance=area,
            confidence="medium" if any(e.url for e in evidence) else "low",
            signal_strength=_MOCK_STRENGTH.get(cat, 3),
            evidence=evidence,
        ))
    not_evidenced = [c for c in SIGNAL_CATEGORIES if c not in by_cat]
    found = ", ".join(sorted(by_cat)) or "none"
    summary = (
        f"{block.company_name} shows recent activity in its sector based on the "
        f"collected evidence. Signals evidenced: {found}; all other categories "
        f"are not evidenced. DRY-RUN output — run with --live for a real Opus 4.8 "
        f"interpretation before acting on this."
    )
    return signals, not_evidenced, summary


# ─────────────────────────────────────────────────────────────────────────────
# Entry point + review flags
# ─────────────────────────────────────────────────────────────────────────────

def interpret_and_score(cfg: EngineConfig, block: EvidenceBlock,
                        today: date | None = None) -> tuple[list[ScoredSignal], list[str], str]:
    signals, not_evidenced, summary = (
        live_interpret(cfg, block) if cfg.live else mock_interpret(block))
    return ([score_signal(cfg, s, today) for s in signals], not_evidenced, summary)


def review_flag(scored: list[ScoredSignal]) -> tuple[bool, str | None]:
    """Per-company review flags (boilerplate detection is cross-company, in runner)."""
    reasons = []
    for s in scored:
        if s.signal.confidence == "high" and not any(e.url for e in s.signal.evidence):
            reasons.append(f"{s.signal.category}: high confidence but no verifiable source")
        if s.signal.confidence == "high" and not any(e.event_date for e in s.signal.evidence):
            reasons.append(f"{s.signal.category}: high confidence but no approximate date")
    return (bool(reasons), "; ".join(reasons) or None)
