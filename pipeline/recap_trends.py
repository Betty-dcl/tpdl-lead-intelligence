"""Mega-cap trend synthesis — chantier 2/4 extension, Betty's explicit
2026-09-07 request ("tu es capable de comprendre les news et generaliser des
trends ?" / "go - toujours clair et pro"). See `recap.py`'s module docstring
for why this lives in its own file/table/CLI flag rather than touching the
base watch's verbatim-only discipline.

Reads ALREADY-STORED `MegaCapRecap` facts back out of the DB — no new
discovery, no new Serper/Exa/Firecrawl spend. One Sonnet call per company,
over facts already verified verbatim by `recap.verbatim_qa_recap`.

The guardrail: a summary is stored ONLY if at least one of its cited
`supporting_quotes` is an exact match to one of the facts it was given.
Zero verified citations ⇒ the whole summary is discarded, never stored —
cited-but-fabricated evidence is worse than no summary at all.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from pipeline import extract as extract_mod
from pipeline.config import PROMPTS_DIR, EngineConfig, require_live

logger = logging.getLogger(__name__)

TREND_PROMPT = (PROMPTS_DIR / "recap_trend_sonnet.md").read_text(encoding="utf-8")
MAX_FACTS_PER_COMPANY = 40  # sanity cap, mirrors MAX_ITEMS_PER_COMPANY elsewhere


@dataclass
class TrendCandidate:
    summary: str
    supporting_quotes: list[str]


def _parse_trend_response(text: str) -> TrendCandidate | None:
    candidate = extract_mod._json_object(text) or text
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        logger.warning("[recap_trends] unparseable trend response (len=%d)", len(text))
        return None
    summary = payload.get("summary")
    quotes = payload.get("supporting_quotes")
    if not summary or not isinstance(quotes, list):
        return None
    return TrendCandidate(
        summary=summary.strip(),
        supporting_quotes=[q for q in quotes if isinstance(q, str) and q],
    )


def qa_trend_candidate(candidate: TrendCandidate, facts: list[str]
                       ) -> tuple[TrendCandidate | None, list[str]]:
    """Fail-closed citation check: every `supporting_quote` must be an exact
    substring of one of the facts the model was actually given. A summary
    with zero verified quotes is rejected outright."""
    corpus = " ||| ".join(facts)
    verified: list[str] = []
    violations: list[str] = []
    for q in candidate.supporting_quotes:
        if q in corpus:
            verified.append(q)
        else:
            violations.append(f"quote not found in given facts: {q[:100]!r}")
    if not verified:
        violations.append("summary discarded: 0 verified citations")
        return None, violations
    return TrendCandidate(summary=candidate.summary, supporting_quotes=verified), violations


def build_trend_prompt(company: str, facts: list[str]) -> str:
    facts_block = "\n".join(f"- {f}" for f in facts[:MAX_FACTS_PER_COMPANY])
    return f"COMPANY: {company}\n\nFACTS (verbatim, already verified):\n{facts_block}"


def summarize_company_trend(cfg: EngineConfig, company: str, facts: list[str]
                            ) -> TrendCandidate | None:
    """One live Sonnet call. `facts` must be the exact verbatim `quote`
    strings already stored in MegaCapRecap for this company — NOT
    `summary_text`, which may carry an `[unconfirmed]` prefix that is not
    itself part of the source document and would fail the citation check."""
    if not facts:
        return None
    require_live(cfg, cfg.anthropic_api_key, "Mega-cap trend synthesis (Sonnet 5)")
    import anthropic

    client = anthropic.Anthropic(api_key=cfg.anthropic_api_key)
    response = client.messages.create(
        model=cfg.extraction_model,
        max_tokens=1024,
        system=TREND_PROMPT,
        messages=[{"role": "user", "content": build_trend_prompt(company, facts)}],
    )
    text = "".join(b.text for b in response.content if b.type == "text")
    from pipeline.usage_log import log_anthropic_call
    log_anthropic_call(cfg.extraction_model, response.usage, company, "recap_trend")

    candidate = _parse_trend_response(text)
    if candidate is None:
        logger.warning("[recap_trends] %s: unparseable response, no summary stored", company)
        return None
    verified, violations = qa_trend_candidate(candidate, facts)
    for v in violations:
        logger.warning("[recap_trends] %s: %s", company, v)
    return verified


def write_trend_summary(db, company: str, candidate: TrendCandidate,
                        facts_considered: int, model: str) -> None:
    from app.models import MegaCapTrendSummary

    db.add(MegaCapTrendSummary(
        company_name=company,
        generated_at=datetime.now(timezone.utc),
        summary_text=candidate.summary,
        supporting_quotes=json.dumps(candidate.supporting_quotes),
        facts_considered=facts_considered,
        model=model,
    ))
    db.commit()
