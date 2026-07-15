"""Step 3 — Extraction (Sonnet 5): raw docs → verbatim evidence items.

The anti-hallucination guarantee is enforced in CODE, not just in the prompt:
`verbatim_qa()` rejects any quote that is not an exact substring of a source
document. A strong model may be tempted to editorialise — it cannot get an
editorialised sentence past this check.

Dry-run: `mock_extract()` walks the fixture docs and lifts sentences verbatim,
exercising the exact same contract with zero API calls.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime

from pipeline.config import PROMPTS_DIR, EngineConfig, require_live
from pipeline.types import SIGNAL_CATEGORIES, EvidenceBlock, EvidenceItem, RawDoc

logger = logging.getLogger(__name__)

EXTRACT_PROMPT = (PROMPTS_DIR / "extract_sonnet.md").read_text(encoding="utf-8")

MAX_ITEMS_PER_COMPANY = 24  # sanity cap


# ─────────────────────────────────────────────────────────────────────────────
# QA — the verbatim lock, enforced in code
# ─────────────────────────────────────────────────────────────────────────────

def _normalise(text: str) -> str:
    """Whitespace-insensitive comparison basis (newlines in sources vary)."""
    return re.sub(r"\s+", " ", text).strip().lower()


def verbatim_qa(items: list[EvidenceItem], docs: list[RawDoc]) -> tuple[list[EvidenceItem], list[str]]:
    """Split extraction output into (accepted, violations).

    A quote is accepted only if it appears verbatim (modulo whitespace) inside
    at least one source document. Everything else is a violation — logged and
    DROPPED, never scored.

    Attribution: a quote must appear in the doc(s) matching its OWN declared
    source. If it appears only in a DIFFERENT source, it is still kept (the
    sentence is real) but a `SOURCE MISMATCH` violation is recorded — a wrong
    label would otherwise silently inflate corroboration (distinct sources/URLs).
    """
    # Concatenate per source: two docs sharing a source must BOTH stay in the
    # haystack (a plain dict comprehension would keep only the last one).
    by_source: dict[str, list[str]] = {}
    for d in docs:
        by_source.setdefault(d.source, []).append(_normalise(d.title + " " + d.text))
    corpus = {src: " ||| ".join(texts) for src, texts in by_source.items()}
    all_text = " ||| ".join(corpus.values())

    accepted: list[EvidenceItem] = []
    violations: list[str] = []
    for item in items:
        if not item.quote or item.category not in SIGNAL_CATEGORIES:
            violations.append(f"malformed item: {item!r}")
            continue
        needle = _normalise(item.quote)
        if needle in corpus.get(item.source, ""):
            accepted.append(item)                       # in its own declared source
        elif needle in all_text:
            accepted.append(item)                       # real, but mis-attributed
            violations.append(
                f"SOURCE MISMATCH [{item.category}]: quote not in declared "
                f"source {item.source!r}: {item.quote[:100]!r}")
        else:
            violations.append(f"NOT VERBATIM [{item.category}]: {item.quote[:120]!r}")
    return accepted, violations


# ─────────────────────────────────────────────────────────────────────────────
# Live extraction (Sonnet 5) — behind the money gate
# ─────────────────────────────────────────────────────────────────────────────

def _docs_payload(docs: list[RawDoc]) -> str:
    blocks = []
    for d in docs:
        blocks.append(
            f"=== DOCUMENT source={d.source} url={d.url or 'null'} "
            f"published={d.published or 'null'} ===\n{d.title}\n{d.text}"
        )
    return "\n\n".join(blocks)


def live_extract(cfg: EngineConfig, company: str, docs: list[RawDoc]) -> list[EvidenceItem]:
    require_live(cfg, cfg.anthropic_api_key, "Extraction (Sonnet 5)")
    import anthropic

    client = anthropic.Anthropic(api_key=cfg.anthropic_api_key)
    response = client.messages.create(
        model=cfg.extraction_model,
        max_tokens=4096,
        system=EXTRACT_PROMPT,
        messages=[{
            "role": "user",
            "content": f"COMPANY: {company}\n\nRAW DOCUMENTS:\n\n{_docs_payload(docs)}",
        }],
    )
    text = "".join(b.text for b in response.content if b.type == "text")
    return _parse_items(text)


def _parse_items(text: str) -> list[EvidenceItem]:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return []
    try:
        payload = json.loads(m.group())
    except json.JSONDecodeError:
        logger.warning("[extract] unparseable JSON from model")
        return []
    items = []
    for raw in payload.get("items", [])[:MAX_ITEMS_PER_COMPANY]:
        quote = raw.get("quote", "")
        # Backstop: if the model returned no date but the quote states one,
        # recover it deterministically (never guess — regex on the quote only).
        event_date = _parse_iso(raw.get("event_date")) or date_in_text(quote)
        items.append(EvidenceItem(
            quote=quote,
            source=raw.get("source", ""),
            url=raw.get("url") or None,
            event_date=event_date,
            category=raw.get("category", ""),
        ))
    return items


def _parse_iso(value) -> date | None:
    if not value or value == "null":
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Dates stated IN the text — more reliable than the article's publish date
# ("effective 1 June 2026" is the event date; the article may be older/newer)
# ─────────────────────────────────────────────────────────────────────────────

_MONTHS = {m.lower(): i for i, m in enumerate(
    ("January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"), start=1)}
_MONTHS.update({m[:3]: i for m, i in list(_MONTHS.items())})  # jan, feb, …

_DATE_PATTERNS = (
    # 2026-06-01
    re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"),
    # 1 June 2026 / 01 Jun 2026
    re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3,9})\.?\s+(\d{4})\b"),
    # June 1, 2026 / Jun 1 2026
    re.compile(r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b"),
    # June 2026 (month only → 1st of month)
    re.compile(r"\b([A-Za-z]{3,9})\.?\s+(\d{4})\b"),
)


def _date_from_match(pattern, groups) -> date | None:
    try:
        if pattern is _DATE_PATTERNS[0]:
            return date(int(groups[0]), int(groups[1]), int(groups[2]))
        if pattern is _DATE_PATTERNS[1]:
            month = _MONTHS.get(groups[1].lower()[:3])
            return date(int(groups[2]), month, int(groups[0])) if month else None
        if pattern is _DATE_PATTERNS[2]:
            month = _MONTHS.get(groups[0].lower()[:3])
            return date(int(groups[2]), month, int(groups[1])) if month else None
        month = _MONTHS.get(groups[0].lower()[:3])
        return date(int(groups[1]), month, 1) if month else None
    except ValueError:
        return None


def date_in_text(text: str, today: date | None = None) -> date | None:
    """Best plausible date stated in the text, or None. Never guesses a year.

    Guardrails (fix for the "wrong date" risk): dates in the future or older
    than 5 years are discarded; among the rest the MOST RECENT is returned
    (an event date like "appointed June 2026" beats stale context like
    "founded in 2019 ... appointed June 2026").
    """
    today = today or date.today()
    cands: list[date] = []
    for pattern in _DATE_PATTERNS:
        for m in pattern.finditer(text):
            d = _date_from_match(pattern, m.groups())
            if d and d <= today and (today - d).days <= 365 * 5:
                cands.append(d)
    return max(cands) if cands else None


# Speculation / negation / rumour markers — a quote containing one of these is
# kept but FLAGGED for review: the verbatim lock proves the sentence is real,
# not that the event actually happened (fix for the "sense not checked" gap).
# Matched on WORD BOUNDARIES (see has_negation) so "not" doesn't fire inside
# "cannot"/"another" and "may" doesn't fire inside "Mayer". Multi-word markers
# match as phrases. Hedges kept deliberately narrow to limit false review noise.
_NEGATION_MARKERS = (
    "not", "no longer", "denied", "denies", "deny", "rumour", "rumor",
    "reportedly", "allegedly", "considering", "may", "might", "could",
    "would", "plans to", "planning to", "expected to", "is set to",
    "in talks", "explores", "exploring", "potential", "speculation",
)

_NEGATION_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(m) for m in _NEGATION_MARKERS) + r")\b")


def has_negation(text: str) -> bool:
    """True if the quote hedges/negates — kept but flagged (event may not have happened)."""
    return bool(_NEGATION_RE.search(text.lower()))


# ─────────────────────────────────────────────────────────────────────────────
# Dry-run extraction — verbatim sentence lifting, zero API
# ─────────────────────────────────────────────────────────────────────────────

_CATEGORY_HINTS: dict[str, tuple[str, ...]] = {
    # Order matters (first match wins): most specific first — "private equity
    # fund acquired a stake" must classify as pe_event, not ma_expansion.
    "pe_event": ("private equity", "buyout", "investment from", "stake",
                 "go-private", "majority"),
    "leadership_change": ("ceo", "chief executive", "president", "appointed",
                          "appointment", "steps down", "succeed"),
    "hiring": ("hiring", "job opening", "positions", "recruit", "vacanc"),
    "ma_expansion": ("acquisition", "acquire", "merger", "expansion", "expands"),
    "digital_initiative": ("crm", "digital transformation", "data platform",
                           "omnichannel", "analytics programme", "analytics program"),
    "org_restructuring": ("restructuring", "reorganisation", "reorganization",
                          "operating model", "cost programme", "cost program"),
}

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def mock_extract(company: str, docs: list[RawDoc]) -> list[EvidenceItem]:
    """Deterministic stand-in for Sonnet 5: lift matching sentences VERBATIM.

    Same contract, same QA, zero cost. Good enough to validate the whole
    chain and the CSV round-trip before spending a cent.
    """
    items: list[EvidenceItem] = []
    for doc in docs:
        for sentence in _SENTENCE_SPLIT.split(doc.text):
            s = sentence.strip()
            if len(s) < 25:
                continue
            low = s.lower()
            for category, hints in _CATEGORY_HINTS.items():
                if any(h in low for h in hints):
                    items.append(EvidenceItem(
                        quote=s,  # exact substring — passes verbatim_qa by construction
                        source=doc.source,
                        url=doc.url,
                        # date stated in the sentence beats the publish date
                        event_date=date_in_text(s) or doc.published,
                        category=category,
                    ))
                    break
            if len(items) >= MAX_ITEMS_PER_COMPANY:
                return items
    return items


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def extract(cfg: EngineConfig, company: str, sector: str | None,
            docs: list[RawDoc], tech_stack: str | None = None
            ) -> tuple[EvidenceBlock, list[str], list[str]]:
    """Docs → QA-checked EvidenceBlock, verbatim violations, and review flags.

    Returns (block, violations, flags):
      - violations: quotes DROPPED because they were not verbatim.
      - flags: kept quotes that contain speculation/negation markers → the
        company is review-flagged so a human checks the event really happened.
    """
    raw_items = (live_extract(cfg, company, docs) if cfg.live
                 else mock_extract(company, docs))
    accepted, violations = verbatim_qa(raw_items, docs)
    if violations:
        logger.warning("[extract] %s: %d verbatim violations dropped",
                       company, len(violations))
    flags = [f"speculative/negated evidence [{it.category}]: {it.quote[:80]}"
             for it in accepted if has_negation(it.quote)]
    if flags:
        logger.info("[extract] %s: %d quote(s) flagged for review (negation/speculation)",
                    company, len(flags))
    block = EvidenceBlock(
        company_name=company,
        sector=sector,
        items=accepted,
        tech_stack_summary=tech_stack,
    )
    return block, violations, flags
