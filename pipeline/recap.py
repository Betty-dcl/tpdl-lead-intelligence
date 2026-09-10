"""Mega-cap trend-watch ("recap") mode — CLI `--recap`, chantier 2/4 of the
2026-09-01 Nathalie meeting recap (see .claude/state.md).

Structurally separate from the scored pipeline: reuses the same research
primitives (Serper/SerpAPI news, Exa, Firecrawl, Perplexity) but a SMALLER
source set, a DIFFERENT verbatim-lock extraction pass (its own prompt/category
set — product launches ARE in scope here, unlike the scored pipeline), and
NEVER calls score.interpret_and_score(). No Opus call, no assessed_score, no
CompanyResult. Output is a plain list of verbatim facts, filed by category —
`MegaCapRecap` rows + a CSV — never a narrative synthesised by a model.

The ONE deliberate exception (2026-09-07, Betty's explicit request) is
`pipeline/recap_trends.py` — a separate, opt-in module that reads these
already-verified facts back out and asks a model for a short trend synthesis
per company. It never touches this module's verbatim-lock discipline: it's a
distinct file, distinct table (`MegaCapTrendSummary`), distinct CLI flag, and
its own citation-based guardrail (a summary citing zero real quotes from the
facts it was given is rejected, never stored).

Manual CLI invocation only (`python -m pipeline.runner --recap --names "..."
--live`), roughly every 3-4 months. No agent chat command, no UI page, no
scheduler — same "nothing automatic" doctrine as the rest of this repo.
"""
from __future__ import annotations

import csv
import json
import logging
import re
from datetime import datetime
from pathlib import Path

from pipeline import extract as extract_mod
from pipeline import research
from pipeline.config import PROMPTS_DIR, EngineConfig, require_live
from pipeline.types import RECAP_CATEGORIES, RawDoc, RecapItem

logger = logging.getLogger(__name__)

RECAP_PROMPT = (PROMPTS_DIR / "recap_sonnet.md").read_text(encoding="utf-8")
MAX_ITEMS_PER_COMPANY = 24  # same sanity cap as the scored pipeline's extraction


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 (recap-scoped) — a SMALLER source pool than the scored pipeline's 9:
# no EU registry, no job-board search, no social scan — none of those serve
# "new products/M&A/tech platform" for a mega-cap that already dominates search.
# ─────────────────────────────────────────────────────────────────────────────

# Investor/press subpaths tried before falling back to the flat homepage scrape.
# Deterministic, fail-open: the first non-empty scrape wins (cheap — one
# Firecrawl credit per candidate tried, not per company).
_IR_SUBPATHS = ("/investors", "/investor-relations", "/en/investors",
                "/news", "/press-releases", "/media/press-releases")


def ir_sources(cfg: EngineConfig, website: str | None) -> list[RawDoc]:
    """Try well-known investor/press subpaths, then the flat homepage. Never
    raises — a mega-cap with no reachable site simply contributes no IR docs."""
    if not website:
        return []
    base = (website if website.startswith("http") else f"https://{website}").rstrip("/")
    for suffix in _IR_SUBPATHS:
        try:
            docs = research.firecrawl_fetch(cfg, base + suffix)
        except Exception:
            docs = []
        if docs:
            return docs
    try:
        return research.firecrawl_fetch(cfg, base)
    except Exception:
        return []


def financial_statement_query(cfg: EngineConfig, company: str) -> list[RawDoc]:
    """Perplexity Sonar, worded toward annual report/10-K/investor-day/earnings-
    call content — same fail-open contract as research.perplexity_sonar()."""
    require_live(cfg, cfg.perplexity_api_key, "Perplexity Sonar (recap)")
    data = research._post_json(
        "https://api.perplexity.ai/chat/completions",
        {
            "model": "sonar",
            "messages": [{
                "role": "user",
                "content": (
                    f"Recent annual report, 10-K, investor day, or earnings call "
                    f"commentary from {company} about new product launches, M&A/"
                    f"partnerships, or technology/CRM platform initiatives. Report "
                    f"only dated facts. If none, say 'none found'."
                ),
            }],
        },
        {"Authorization": f"Bearer {cfg.perplexity_api_key}"},
    )
    text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    if not text or "none found" in text.lower():
        return []
    return [RawDoc(source="perplexity_recap", url=None,
                   title=f"Financial statements — {company}", text=text)]


def gather_recap(cfg: EngineConfig, company: str, website: str | None = None) -> list[RawDoc]:
    """Assemble the recap-scoped doc pool for one company. Fail-open per
    source: a source erroring or offline simply contributes nothing."""
    docs: list[RawDoc] = []
    for fn in (
        lambda: research.serp_news(cfg, company),
        lambda: research.exa_search(cfg, company),
        lambda: ir_sources(cfg, website),
        lambda: financial_statement_query(cfg, company),
    ):
        try:
            docs.extend(fn())
        except Exception as exc:
            logger.info("[recap] source skipped for %s: %s", company, exc)
    return research.dedupe(docs)


# ─────────────────────────────────────────────────────────────────────────────
# Step 3 (recap-scoped) — verbatim-locked extraction, own category set,
# duplicated (not parametrised) QA/parsing so the two taxonomies can never
# quietly merge — see module docstring + RecapItem's own docstring.
# ─────────────────────────────────────────────────────────────────────────────

def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def verbatim_qa_recap(items: list[RecapItem], docs: list[RawDoc]
                      ) -> tuple[list[RecapItem], list[str]]:
    """Same anti-hallucination contract as extract.verbatim_qa(), checked
    against RECAP_CATEGORIES instead of SIGNAL_CATEGORIES."""
    by_source: dict[str, list[str]] = {}
    for d in docs:
        by_source.setdefault(d.source, []).append(_normalise(d.title + " " + d.text))
    corpus = {src: " ||| ".join(texts) for src, texts in by_source.items()}
    all_text = " ||| ".join(corpus.values())

    accepted: list[RecapItem] = []
    violations: list[str] = []
    for item in items:
        if not item.quote or item.category not in RECAP_CATEGORIES:
            violations.append(f"malformed recap item: {item!r}")
            continue
        needle = _normalise(item.quote)
        if needle in corpus.get(item.source, ""):
            accepted.append(item)
        elif needle in all_text:
            accepted.append(item)
            violations.append(
                f"SOURCE MISMATCH [{item.category}]: quote not in declared "
                f"source {item.source!r}: {item.quote[:100]!r}")
        else:
            violations.append(f"NOT VERBATIM [{item.category}]: {item.quote[:120]!r}")
    return accepted, violations


def _parse_recap_items(text: str) -> list[RecapItem]:
    candidate = extract_mod._json_object(text) or text
    try:
        payload = json.loads(candidate)
        raw_items = payload.get("items", [])
    except json.JSONDecodeError:
        raw_items = extract_mod._salvage_item_dicts(candidate)
        logger.warning("[recap] broken JSON from model (len=%d) — salvaged %d item(s)",
                       len(candidate), len(raw_items))
    items = []
    for raw in raw_items[:MAX_ITEMS_PER_COMPANY]:
        quote = raw.get("quote", "")
        event_date = extract_mod._parse_iso(raw.get("event_date")) or extract_mod.date_in_text(quote)
        items.append(RecapItem(
            quote=quote,
            source=raw.get("source", ""),
            url=raw.get("url") or None,
            event_date=event_date,
            category=raw.get("category", ""),
        ))
    return items


def live_extract_recap(cfg: EngineConfig, company: str, docs: list[RawDoc]) -> list[RecapItem]:
    require_live(cfg, cfg.anthropic_api_key, "Recap extraction (Sonnet 5)")
    import anthropic

    client = anthropic.Anthropic(api_key=cfg.anthropic_api_key)
    items: list[RecapItem] = []
    chunks = ([docs[i:i + extract_mod.CHUNK_DOCS]
              for i in range(0, len(docs), extract_mod.CHUNK_DOCS)] or [[]])
    for chunk in chunks:
        response = client.messages.create(
            model=cfg.extraction_model,
            max_tokens=16384,
            system=RECAP_PROMPT,
            messages=[{
                "role": "user",
                "content": f"COMPANY: {company}\n\nRAW DOCUMENTS:\n\n{extract_mod._docs_payload(chunk)}",
            }],
        )
        text = "".join(b.text for b in response.content if b.type == "text")
        from pipeline.usage_log import log_anthropic_call
        log_anthropic_call(cfg.extraction_model, response.usage, company, "recap_extract")
        items.extend(_parse_recap_items(text))
    return items[:MAX_ITEMS_PER_COMPANY]


# Category hints for the dry-run stand-in — deliberately distinct from
# extract.py's _CATEGORY_HINTS (different taxonomy, "other" has no hint list
# by design: it is a manual/rare bucket, never guessed).
_RECAP_HINTS: dict[str, tuple[str, ...]] = {
    "ma_activity": ("acquisition", "acquire", "merger", "divest", "joint venture", "partnership"),
    "tech_platform": ("crm", "digital platform", "digital transformation", "data platform"),
    "new_product": ("launch", "launches", "approval", "approved", "pipeline",
                    "phase 3", "phase iii", "fda approves", "ema approves"),
    "capacity_investment": ("manufacturing", "campus", "capex", "expand", "expansion",
                            "facility", "plant", "million investment", "billion investment"),
    "leadership_change": ("appoint", "appoints", "appointed", "elect", "elected",
                          "retire", "retirement", "steps down", "names new",
                          "chief executive", "chief financial", "chairman"),
    "legal_regulatory": ("lawsuit", "litigation", "settlement", "settles", "fda warns",
                         "fda warning", "recall", "withdrawn from the market"),
    "restructuring": ("layoffs", "layoff", "job cuts", "cost-cutting", "cost cutting",
                      "restructuring", "site closure"),
}
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def mock_extract_recap(company: str, docs: list[RawDoc]) -> list[RecapItem]:
    """Deterministic dry-run stand-in, same contract/QA as live, zero cost."""
    items: list[RecapItem] = []
    for doc in docs:
        for sentence in _SENTENCE_SPLIT.split(doc.text):
            s = sentence.strip()
            if len(s) < 25:
                continue
            low = s.lower()
            for category, hints in _RECAP_HINTS.items():
                if any(h in low for h in hints):
                    items.append(RecapItem(
                        quote=s, source=doc.source, url=doc.url,
                        event_date=extract_mod.date_in_text(s) or doc.published,
                        category=category,
                    ))
                    break
            if len(items) >= MAX_ITEMS_PER_COMPANY:
                return items
    return items


def extract_recap(cfg: EngineConfig, company: str, docs: list[RawDoc]
                  ) -> tuple[list[RecapItem], list[str]]:
    """Docs → QA-checked recap items + verbatim violations. NEVER scores."""
    raw_items = (live_extract_recap(cfg, company, docs) if cfg.live
                else mock_extract_recap(company, docs))
    accepted, violations = verbatim_qa_recap(raw_items, docs)
    if violations:
        logger.warning("[recap] %s: %d verbatim violations dropped", company, len(violations))
    return accepted, violations


# ─────────────────────────────────────────────────────────────────────────────
# Output — deterministic summary line (NO model-written synthesis, ever — see
# module docstring), DB rows, CSV export.
# ─────────────────────────────────────────────────────────────────────────────

def summarize_item(item: RecapItem) -> str:
    """Deterministic, non-LLM one-line summary. A hedged quote is prefixed
    [unconfirmed] rather than silently dropping the negation signal.

    No category prefix here (was `[{category}] quote` until 2026-09-07) —
    `category` is already its own stored column and the dashboard groups/
    badges facts by it, so baking the label into the text too just repeated
    the same word the reader is already looking at (Betty: "ça va pas
    d'afficher les news products tjrs" — every fact under the New Product
    header re-said "[new_product]")."""
    prefix = "[unconfirmed] " if extract_mod.has_negation(item.quote) else ""
    return f"{prefix}{item.quote[:200]}"


def write_recap_rows(db, company: str, run_date: datetime, items: list[RecapItem]) -> int:
    """Persist one MegaCapRecap row per accepted item. Append-only."""
    from app.models import MegaCapRecap

    for it in items:
        db.add(MegaCapRecap(
            company_name=company,
            run_date=run_date,
            category=it.category,
            summary_text=summarize_item(it),
            quote=it.quote,
            source=it.source,
            url=it.url,
            event_date=(datetime.combine(it.event_date, datetime.min.time())
                       if it.event_date else None),
        ))
    db.commit()
    return len(items)


RECAP_CSV_HEADERS = ["Company Name", "Run Date", "Category", "Summary",
                     "Quote", "Source", "URL", "Event Date"]


def export_recap_csv(company_items: list[tuple[str, list[RecapItem]]],
                     run_date: datetime, path: Path) -> Path:
    """Courtesy export (not the source of truth — MegaCapRecap rows are):
    one row per accepted item, human-shareable without opening the DB."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=RECAP_CSV_HEADERS)
        writer.writeheader()
        for company, items in company_items:
            for it in items:
                writer.writerow({
                    "Company Name": company,
                    "Run Date": run_date.date().isoformat(),
                    "Category": it.category,
                    "Summary": summarize_item(it),
                    "Quote": it.quote,
                    "Source": it.source,
                    "URL": it.url or "",
                    "Event Date": it.event_date.isoformat() if it.event_date else "",
                })
    return path
