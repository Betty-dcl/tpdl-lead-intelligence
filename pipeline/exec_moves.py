"""Executive moves — discovery + verbatim extraction (chantier 4/4 Slice 1,
2026-09-01 Nathalie meeting recap; .claude/state.md).

Industry-wide, NOT per-company: a handful of Serper News queries + one Exa
neural search covering the whole pharma/life-science/biotech/medtech industry
replace what would otherwise be 620× per-company calls — this is exactly the
shape Nathalie asked for ("chaque semaine 10 personnes"), a small bounded
weekly batch, not a full-universe scan. Two sources, not one (Betty,
2026-09-02: "tu es sûr qu'il n'y a pas d'autres sources intéressantes?") —
Serper's keyword search and Exa's semantic search cover different phrasings
of the same announcement, mirroring the two-source pattern the main scored
pipeline already uses per company (research.py's serp_news + exa_search).

No Opus/interpretation step: a move is a FACT, not a scored opinion. The
C-suite/-1/-2 filter (app/tools/exec_titles.py) and geography tagging happen
with cheap deterministic code on the accepted candidates — never a second LLM
call. Same verbatim-lock doctrine as pipeline/extract.py, but its own schema
(ExecMoveCandidate) and its own duplicated QA (never shared with
extract.verbatim_qa — this data concerns named individuals; the anti-
hallucination guarantee must stay simple to audit per call site).

LinkedIn is explicitly NOT part of automated discovery (Nathalie's own risk
flag) and connection-request sending is ALWAYS 100% human (decision Betty,
2026-09-02) — this module only detects + stores + lets a human review.

Own small CLI entrypoint (separate from pipeline/runner.py's per-company flag
surface, since this is industry-wide, not company-scoped):
    python pipeline/exec_moves.py --live
Manual Terminal invocation only, same "nothing automatic" doctrine as the
rest of this repo. `require_live()` gate reused as-is: no key/no --live ⇒ [].
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import unicodedata

from pipeline import extract as extract_mod
from pipeline import research
from pipeline.config import PROMPTS_DIR, EngineConfig, require_live
from pipeline.types import ExecMoveCandidate, RawDoc

logger = logging.getLogger(__name__)

EXEC_MOVES_PROMPT = (PROMPTS_DIR / "exec_moves_sonnet.md").read_text(encoding="utf-8")
MAX_ITEMS = 60          # sanity cap on one extraction pass
CHUNK_DOCS = extract_mod.CHUNK_DOCS

# ─────────────────────────────────────────────────────────────────────────────
# Step 1 — discovery (industry-wide news search, bounded query budget)
# ─────────────────────────────────────────────────────────────────────────────

MAX_QUERIES = 10           # weekly ~10-person volume, not a scan
RESULTS_PER_QUERY = 10

_ANNOUNCE_TERMS = '"pleased to announce" OR "appointed" OR "joins as" OR "named"'
_TITLE_TERMS = (
    '"Chief Medical Officer" OR "Chief Operating Officer" OR "Chief Information Officer" OR '
    '"Chief Technology Officer" OR "Chief Innovation Officer" OR "Chief Commercial Officer" OR '
    '"Chief Digital Officer" OR "Managing Director" OR "Senior Vice President" OR "Vice President" OR '
    '"General Manager" OR "Deputy General Manager" OR "Senior Director"'
)
_SECTOR_TERMS = 'pharma OR "life sciences" OR biotech OR medtech'


def press_release_query() -> str:
    """The default industry-wide query — pure function, testable without a
    live call. `discover_moves` accepts a custom query list to widen/narrow
    later without touching this default."""
    return f"({_ANNOUNCE_TERMS}) ({_TITLE_TERMS}) ({_SECTOR_TERMS})"


def serp_press_release_search(cfg: EngineConfig, query: str,
                              num: int = RESULTS_PER_QUERY) -> list[RawDoc]:
    """Serper Google News, industry-wide (no company scoping). Fail-open at
    the require_live() gate only — a real HTTP failure propagates so
    discover_moves() (which wraps every query in try/except) can log it."""
    require_live(cfg, cfg.serper_api_key, "Serper News (exec moves)")
    data = research._post_json(
        "https://google.serper.dev/news",
        {"q": query, "num": num},
        {"X-API-KEY": cfg.serper_api_key},
    )
    return [
        RawDoc(
            source="serper_news_moves",
            url=item.get("link"),
            title=item.get("title", ""),
            text=item.get("snippet", ""),
            published=research._parse_date(item.get("date")),
        )
        for item in data.get("news", [])
    ]


_EXA_QUERY = (
    "pharmaceutical life sciences biotech medtech company announces new Chief "
    "Medical Officer Chief Operating Officer Chief Technology Officer Chief "
    "Innovation Officer Senior Vice President General Manager appointment"
)


def exa_moves_search(cfg: EngineConfig, query: str = _EXA_QUERY, num: int = 15) -> list[RawDoc]:
    """Exa neural search — industry-wide (no company scoping), complements
    Serper's keyword search with semantic recall (same two-source pattern
    the main scored pipeline already uses per company: research.py's
    serp_news + exa_search)."""
    require_live(cfg, cfg.exa_api_key, "Exa (exec moves)")
    data = research._post_json(
        "https://api.exa.ai/search",
        {"query": query, "numResults": num, "contents": {"text": {"maxCharacters": 2000}}},
        {"x-api-key": cfg.exa_api_key},
    )
    return [
        RawDoc(
            source="exa_moves",
            url=item.get("url"),
            title=item.get("title") or "",
            text=(item.get("text") or "")[:2000],
            published=research._parse_date(item.get("publishedDate")),
        )
        for item in data.get("results", [])
    ]


def discover_moves(cfg: EngineConfig, queries: list[str] | None = None) -> list[RawDoc]:
    """Loop the query set (default: one broad industry query) plus Exa's
    semantic search, fail-open per source — a bad query, a missing key, or a
    transient error never kills the whole batch."""
    queries = (queries or [press_release_query()])[:MAX_QUERIES]
    docs: list[RawDoc] = []
    for q in queries:
        try:
            docs.extend(serp_press_release_search(cfg, q))
        except Exception as exc:
            logger.info("[exec_moves] Serper discovery query skipped: %s", exc)
    try:
        docs.extend(exa_moves_search(cfg))
    except Exception as exc:
        logger.info("[exec_moves] Exa discovery skipped: %s", exc)
    return research.dedupe(docs)


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — verbatim-locked extraction (Sonnet 5, own schema, own QA)
# ─────────────────────────────────────────────────────────────────────────────

def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def verbatim_qa_moves(candidates: list[ExecMoveCandidate], docs: list[RawDoc]
                      ) -> tuple[list[ExecMoveCandidate], list[str]]:
    """Same anti-hallucination contract as extract.verbatim_qa(): a quote is
    accepted only if it appears verbatim in a source document. This data
    concerns named individuals, so a malformed/unverifiable candidate is
    dropped, never guessed at."""
    by_source: dict[str, list[str]] = {}
    for d in docs:
        by_source.setdefault(d.source, []).append(_normalise(d.title + " " + d.text))
    corpus = {src: " ||| ".join(texts) for src, texts in by_source.items()}
    all_text = " ||| ".join(corpus.values())

    accepted: list[ExecMoveCandidate] = []
    violations: list[str] = []
    for c in candidates:
        if not c.quote or not c.person_name or not c.new_title or not c.new_company:
            violations.append(f"malformed move candidate: {c!r}")
            continue
        needle = _normalise(c.quote)
        if needle in corpus.get(c.source, ""):
            accepted.append(c)
        elif needle in all_text:
            accepted.append(c)
            violations.append(
                f"SOURCE MISMATCH [{c.person_name}]: quote not in declared "
                f"source {c.source!r}: {c.quote[:100]!r}")
        else:
            violations.append(f"NOT VERBATIM [{c.person_name}]: {c.quote[:120]!r}")
    return accepted, violations


def _parse_move_candidates(text: str) -> list[ExecMoveCandidate]:
    candidate = extract_mod._json_object(text) or text
    try:
        payload = json.loads(candidate)
        raw_items = payload.get("moves", [])
    except json.JSONDecodeError:
        raw_items = extract_mod._salvage_item_dicts(candidate)
        logger.warning("[exec_moves] broken JSON from model (len=%d) — salvaged %d item(s)",
                       len(candidate), len(raw_items))
    items = []
    for raw in raw_items[:MAX_ITEMS]:
        quote = raw.get("quote", "")
        if not quote or not raw.get("person_name") or not raw.get("new_title") \
           or not raw.get("new_company"):
            continue
        items.append(ExecMoveCandidate(
            person_name=raw["person_name"],
            new_title=raw["new_title"],
            new_company=raw["new_company"],
            previous_company=raw.get("previous_company") or None,
            previous_title=raw.get("previous_title") or None,
            move_date=extract_mod._parse_iso(raw.get("move_date")) or extract_mod.date_in_text(quote),
            location=raw.get("location") or None,
            quote=quote,
            source=raw.get("source", ""),
            url=raw.get("url") or None,
        ))
    return items


def live_extract_moves(cfg: EngineConfig, docs: list[RawDoc]) -> list[ExecMoveCandidate]:
    require_live(cfg, cfg.anthropic_api_key, "Executive-move extraction (Sonnet 5)")
    import anthropic

    client = anthropic.Anthropic(api_key=cfg.anthropic_api_key)
    items: list[ExecMoveCandidate] = []
    chunks = [docs[i:i + CHUNK_DOCS] for i in range(0, len(docs), CHUNK_DOCS)] or [[]]
    for n, chunk in enumerate(chunks, 1):
        response = client.messages.create(
            model=cfg.extraction_model,
            max_tokens=16384,
            system=EXEC_MOVES_PROMPT,
            messages=[{
                "role": "user",
                "content": f"RAW DOCUMENTS:\n\n{extract_mod._docs_payload(chunk)}",
            }],
        )
        text = "".join(b.text for b in response.content if b.type == "text")
        if response.stop_reason == "max_tokens":
            logger.warning("[exec_moves] chunk %d/%d hit max_tokens (truncated)", n, len(chunks))
        from pipeline.usage_log import log_anthropic_call
        log_anthropic_call(cfg.extraction_model, response.usage, "exec_moves", "exec_moves_extract")
        items.extend(_parse_move_candidates(text))
    return items[:MAX_ITEMS]


def extract_moves(cfg: EngineConfig, docs: list[RawDoc]
                  ) -> tuple[list[ExecMoveCandidate], list[str]]:
    """Docs → QA-checked move candidates + verbatim violations. Requires
    --live (no dry-run stand-in: a plausible-looking but fabricated person/
    title/company is a worse failure mode here than for the scored pipeline,
    so this mirrors pipeline/discovery.py's extraction — live-only)."""
    raw = live_extract_moves(cfg, docs)
    accepted, violations = verbatim_qa_moves(raw, docs)
    if violations:
        logger.warning("[exec_moves] %d verbatim violations dropped", len(violations))
    return accepted, violations


# ─────────────────────────────────────────────────────────────────────────────
# Step 3 — deterministic filter (the ICP gate for this feature) + storage
# ─────────────────────────────────────────────────────────────────────────────

def _norm_dedup(s: str) -> str:
    folded = unicodedata.normalize("NFKD", (s or "").lower())
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", folded).strip()


def compute_dedup_key(person_name: str, new_company: str, new_title: str) -> str:
    """normalized 'person|company|title' — prevents re-inserting the same
    move if a later weekly search surfaces the same press release again."""
    return "|".join(_norm_dedup(x) for x in (person_name, new_company, new_title))


def store_moves(db, candidates: list[ExecMoveCandidate]) -> int:
    """Insert one ExecutiveMove row per candidate whose title is in scope
    (app.tools.exec_titles.is_in_scope — the ICP gate for this feature),
    skipping ones already stored (dedup_key). Never fabricates a field: a
    candidate without any of the required fields was already dropped in
    _parse_move_candidates/verbatim_qa_moves."""
    from app.models import Company, ExecutiveMove
    from app.tools.exec_titles import classify_role_function, classify_seniority_tier
    from app.tools.icp import market_tier

    inserted = 0
    for c in candidates:
        tier = classify_seniority_tier(c.new_title)
        if tier is None:
            continue   # out of scope for this feature (not C-suite/-1/-2)
        key = compute_dedup_key(c.person_name, c.new_company, c.new_title)
        if db.query(ExecutiveMove).filter(ExecutiveMove.dedup_key == key).first():
            continue   # already discovered (same press release re-surfaced)

        resolved = db.get(Company, c.new_company)
        location = c.location or (resolved.location if resolved else None)
        db.add(ExecutiveMove(
            person_name=c.person_name,
            new_title=c.new_title,
            new_company=c.new_company,
            previous_company=c.previous_company,
            previous_title=c.previous_title,
            move_date=c.move_date,
            location=location,
            resolved_company_name=resolved.name if resolved else None,
            seniority_tier=tier,
            role_function=classify_role_function(c.new_title),
            quote=c.quote,
            source_url=c.url,
            source_type="news",
            status="new",
            dedup_key=key,
        ))
        inserted += 1
    db.commit()
    return inserted


# ─────────────────────────────────────────────────────────────────────────────
# CLI — own small entrypoint (industry-wide, not per-company; separate from
# pipeline/runner.py's flag surface)
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="TPDL executive-moves watch")
    parser.add_argument("--live", action="store_true",
                        help="SPENDS MONEY: Serper News search + Sonnet 5 extraction")
    parser.add_argument("--max-queries", type=int, default=MAX_QUERIES)
    args = parser.parse_args()

    if not args.live:
        parser.error("exec_moves requires --live (Serper News search + Sonnet 5 extraction)")

    cfg = EngineConfig.load(live=True)
    docs = discover_moves(cfg)
    logging.getLogger("pipeline.exec_moves").info("[exec_moves] %d raw docs found", len(docs))
    accepted, violations = extract_moves(cfg, docs)

    from app.database import SessionLocal
    with SessionLocal() as db:
        n = store_moves(db, accepted)
    logging.getLogger("pipeline.exec_moves").info(
        "[exec_moves] %d in-scope moves stored (%d candidates, %d QA violations dropped). "
        "Review with Inès's `/moves review` in the dashboard chat.",
        n, len(accepted), len(violations))


if __name__ == "__main__":
    main()
