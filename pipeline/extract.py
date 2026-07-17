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
import unicodedata
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


# Docs per extraction call. Sonnet 5 reasons in prose before its JSON (prefill
# is unsupported on this model, so the preamble can't be suppressed); on a
# 100+-doc corpus that pushed the JSON past max_tokens → truncated → items lost
# (the Grifols/Geistlich flaky zeros). Chunking bounds the OUTPUT of every call:
# fewer docs in → fewer candidate quotes out → truncation structurally cannot
# happen, regardless of corpus size. One chunk ⇒ identical to the old behaviour.
CHUNK_DOCS = 35


def _dedupe_items(items: list[EvidenceItem]) -> list[EvidenceItem]:
    """Drop duplicate quotes across chunks (same normalised quote = one item)."""
    seen: set[str] = set()
    unique: list[EvidenceItem] = []
    for it in items:
        key = _normalise(it.quote)
        if key and key not in seen:
            seen.add(key)
            unique.append(it)
    return unique


def live_extract(cfg: EngineConfig, company: str, docs: list[RawDoc]) -> list[EvidenceItem]:
    require_live(cfg, cfg.anthropic_api_key, "Extraction (Sonnet 5)")
    import anthropic

    client = anthropic.Anthropic(api_key=cfg.anthropic_api_key)
    items: list[EvidenceItem] = []
    chunks = [docs[i:i + CHUNK_DOCS] for i in range(0, len(docs), CHUNK_DOCS)] or [[]]
    for n, chunk in enumerate(chunks, 1):
        response = client.messages.create(
            model=cfg.extraction_model,
            max_tokens=16384,
            system=EXTRACT_PROMPT,
            messages=[{
                "role": "user",
                "content": f"COMPANY: {company}\n\nRAW DOCUMENTS:\n\n{_docs_payload(chunk)}",
            }],
        )
        text = "".join(b.text for b in response.content if b.type == "text")
        if response.stop_reason == "max_tokens":
            # Should be unreachable with chunking; if it happens, the salvage
            # path in _parse_items still recovers every complete item.
            logger.warning("[extract] %s: chunk %d/%d hit max_tokens (truncated)",
                           company, n, len(chunks))
        items.extend(_parse_items(text))
    if len(chunks) > 1:
        logger.info("[extract] %s: %d chunks → %d items before dedupe",
                    company, len(chunks), len(items))
    return _dedupe_items(items)[:MAX_ITEMS_PER_COMPANY]


def _json_object(text: str) -> str | None:
    """Pull the JSON object out of a model reply, tolerating ```json fences and
    surrounding prose. Returns the candidate string or None."""
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    raw = fence.group(1) if fence else text
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    return m.group() if m else None


def _salvage_item_dicts(text: str) -> list[dict]:
    """Recover the COMPLETE item objects from a truncated/broken JSON reply.

    A reply cut mid-array used to cost every item ("unparseable → 0 evidence").
    Item objects are flat (no nested braces), so each complete `{...}` block can
    be parsed independently; only the one item cut in half is lost. Fail-closed:
    anything that doesn't parse or has no quote is skipped, never invented.
    """
    salvaged = []
    for m in re.finditer(r"\{[^{}]*\}", text):
        try:
            d = json.loads(m.group())
        except json.JSONDecodeError:
            continue
        if isinstance(d, dict) and d.get("quote") and d.get("category"):
            salvaged.append(d)
    return salvaged


def _parse_items(text: str) -> list[EvidenceItem]:
    candidate = _json_object(text) or text
    try:
        payload = json.loads(candidate)
        raw_items = payload.get("items", [])
    except json.JSONDecodeError:
        # Truncated or malformed reply: salvage every complete item instead of
        # dropping the whole company (the old "unparseable → 0 evidence" failure).
        raw_items = _salvage_item_dicts(candidate)
        snippet = candidate[:160] + " … " + candidate[-160:] if len(candidate) > 360 else candidate
        logger.warning("[extract] broken JSON from model (len=%d) — salvaged %d "
                       "complete item(s): %s", len(candidate), len(raw_items), snippet)
    items = []
    for raw in raw_items[:MAX_ITEMS_PER_COMPANY]:
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

def _strip_accents(s: str) -> str:
    """février → fevrier, août → aout, März → marz — so one map covers EU sources."""
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


# Month names EN / FR / ES / DE (accent-stripped, lowercase). Targets are
# European (CH/ES + wider life-science watch), so a date in a French, Spanish
# or German source ("1er juin 2026", "15 de junio de 2026", "August 2026") must
# parse too — otherwise recency is silently 0 (the same class of bug that was
# fixed once already for English SERP dates). Same-ordinal names collapse to the
# same month number across languages, so there is no cross-language collision.
_MONTH_NAMES = {
    1:  ("january", "jan", "janvier", "enero", "januar"),
    2:  ("february", "feb", "fevrier", "febrero", "februar"),
    3:  ("march", "mar", "mars", "marzo", "marz"),
    4:  ("april", "apr", "avril", "abril"),
    5:  ("may", "mai", "mayo"),
    6:  ("june", "jun", "juin", "junio", "juni"),
    7:  ("july", "jul", "juillet", "julio", "juli"),
    8:  ("august", "aug", "aout", "agosto"),
    9:  ("september", "sep", "sept", "septembre", "septiembre"),
    10: ("october", "oct", "octobre", "octubre", "oktober"),
    11: ("november", "nov", "novembre", "noviembre"),
    12: ("december", "dec", "decembre", "diciembre", "dezember"),
}
_MONTHS = {name: num for num, names in _MONTH_NAMES.items() for name in names}


def _month_num(token: str) -> int | None:
    """Full-name lookup (accent-stripped). NOT a [:3] truncation — that would
    collapse French juin/juillet to the same 'jui'."""
    return _MONTHS.get(_strip_accents(token).lower())


# A month token is a run of Unicode letters (so accented FR/ES/DE names match);
# 3-12 chars excludes the 2-letter Spanish "de" separator.
_MON = r"[^\W\d_]{3,12}"
# Day ordinals across languages: 1st / 1er / 2e / 2ème / 1º.
_ORD = r"(?:st|nd|rd|th|er|ere|eme|e|º|°)?"

_DATE_PATTERNS = (
    # 2026-06-01
    re.compile(r"\b(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})\b"),
    # Spanish: 15 de junio de 2026  (before the generic form so "de" isn't eaten)
    re.compile(rf"\b(?P<d>\d{{1,2}})\s+de\s+(?P<mon>{_MON})\s+de\s+(?P<y>\d{{4}})\b",
               re.IGNORECASE),
    # 1 June 2026 / 01 Jun 2026 / 1er juin 2026 / 2e mai 2026 / 3. März 2026
    re.compile(rf"\b(?P<d>\d{{1,2}}){_ORD}\.?\s+(?P<mon>{_MON})\.?\s+(?P<y>\d{{4}})\b",
               re.IGNORECASE),
    # June 1, 2026 / Jun 1 2026
    re.compile(rf"\b(?P<mon>{_MON})\.?\s+(?P<d>\d{{1,2}}){_ORD},?\s+(?P<y>\d{{4}})\b",
               re.IGNORECASE),
    # June 2026 / juin 2026 / marzo de 2026 (month only → 1st of month)
    re.compile(rf"\b(?P<mon>{_MON})\.?\s+(?:de\s+)?(?P<y>\d{{4}})\b", re.IGNORECASE),
)


def _date_from_match(match: re.Match) -> date | None:
    g = match.groupdict()
    try:
        year = int(g["y"])
        if g.get("m"):                       # numeric ISO month
            return date(year, int(g["m"]), int(g["d"]))
        month = _month_num(g["mon"])
        if not month:
            return None
        day = int(g["d"]) if g.get("d") else 1
        return date(year, month, day)
    except (ValueError, TypeError):
        return None


def date_in_text(text: str, today: date | None = None) -> date | None:
    """Best plausible date stated in the text, or None. Never guesses a year.

    Guardrails (fix for the "wrong date" risk): dates in the future or older
    than 5 years are discarded; among the rest the MOST RECENT is returned
    (an event date like "appointed June 2026" beats stale context like
    "founded in 2019 ... appointed June 2026"). Parses EN/FR/ES/DE months.
    """
    today = today or date.today()
    cands: list[date] = []
    for pattern in _DATE_PATTERNS:
        for m in pattern.finditer(text):
            d = _date_from_match(m)
            if d and d <= today and (today - d).days <= 365 * 5:
                cands.append(d)
    return max(cands) if cands else None


# Speculation / negation / rumour markers — a quote containing one of these is
# kept but FLAGGED for review: the verbatim lock proves the sentence is real,
# not that the event actually happened (fix for the "sense not checked" gap).
# Matched on WORD BOUNDARIES (see has_negation) so "not" doesn't fire inside
# "cannot"/"another" and "may" doesn't fire inside "Mayer". Multi-word markers
# match as phrases. Hedges kept deliberately narrow to limit false review noise.
# Markers are stored ACCENT-STRIPPED and matched against accent-stripped text,
# so "podría"/"podria", "prévoit"/"prevoit", "erwägt"/"erwagt" all fire.
_NEGATION_MARKERS = (
    # English
    "not", "no longer", "denied", "denies", "deny", "rumour", "rumor",
    "reportedly", "allegedly", "considering", "may", "might", "could",
    "would", "plans to", "planning to", "expected to", "is set to",
    "in talks", "explores", "exploring", "potential", "speculation",
    # French (bare "non"/"ne" deliberately excluded — far too common)
    "envisage", "envisagerait", "pourrait", "en discussions", "en pourparlers",
    "prevoit de", "devrait", "aurait", "rumeur", "presume", "dementi",
    "potentiel", "eventuel", "serait",
    # Spanish (bare "no" deliberately excluded — far too common)
    "podria", "estudia", "en conversaciones", "en negociaciones", "preve",
    "planea", "supuestamente", "presunto", "posible", "niega", "nego",
    # German
    "erwagt", "pruft", "konnte", "in gesprachen", "angeblich", "moglicherweise",
)

_NEGATION_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(m) for m in _NEGATION_MARKERS) + r")\b")


def has_negation(text: str) -> bool:
    """True if the quote hedges/negates — kept but flagged (event may not have happened).

    Accent-insensitive and multilingual (EN/FR/ES/DE): European sources hedge in
    their own language, and an unflagged rumour would otherwise be scored as fact.
    """
    return bool(_NEGATION_RE.search(_strip_accents(text).lower()))


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
