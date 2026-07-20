"""Step -1 — Discovery: find NEW companies from the market watch.

The engine scores a list; it never invented one. The revised scope (Nathalie
16/07, decisions Betty 18/07) wants "top 35 + du NOUVEAU crawlé": a broad
life-science & pharmaceutical watch (subcats dental / dermatology /
diagnostics), Europe-first, no size or listing filter, volume = whatever the
watch finds. This module is that missing capability:

    themes (the 6 signals + the earnings-call angle) → thematic web search
    (Exa neural + SERP news) → Sonnet extracts the company names mentioned as
    the SUBJECT of each finding (verbatim, strict JSON) → drop names already
    in the scored universe → candidate list CSV.

Candidates are NOT scored here — feed them to the normal engine:
    python -m pipeline.runner --names "A;B;C" --live
Money gate: live search + one small Sonnet call (< $0.10 per discovery pass);
dry-run returns the fixture-free empty path without touching the network.
"""
from __future__ import annotations

import csv
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from pipeline.config import EngineConfig, require_live
from pipeline.research import _get_json, _post_json, _serpapi_url

logger = logging.getLogger(__name__)

DEFAULT_OUT = Path("data/csv/discovery_candidates.csv")

# Watch themes = the 6 signal categories + the board/earnings-call angle,
# phrased for the broad life-science scope (Europe-oriented wording; the
# neural search tolerates it, SERP just ranks it lower when absent).
_MARKETS = ("pharmaceutical", "life sciences", "dermatology", "dental", "diagnostics")

DISCOVERY_QUERIES: tuple[tuple[str, str], ...] = (
    ("earnings_call_digital",
     "European pharmaceutical company earnings call digital investment strategic priority"),
    ("earnings_call_digital",
     "life sciences company annual report digital transformation board priority Europe"),
    ("leadership_change",
     "European life sciences company appoints Chief Digital Officer OR Chief Commercial Officer"),
    ("ma_expansion",
     "European dermatology OR dental OR diagnostics company acquisition expansion announcement"),
    ("pe_event",
     "private equity investment European pharmaceutical OR diagnostics company"),
    ("digital_initiative",
     "European pharma company launches CRM data platform commercial digital programme"),
    ("org_restructuring",
     "European life sciences company reorganisation new operating model commercial"),
    ("hiring",
     "European pharmaceutical company hiring commercial digital data leadership roles"),
)

DISCOVER_PROMPT = """You extract COMPANY NAMES from web-search findings.

From the findings below, list every company that is the SUBJECT of a finding
(the company the news is about) and operates in life sciences, pharmaceutical,
dermatology, dental or diagnostics. Rules:
1. Copy the company name EXACTLY as written in the finding. Never invent one.
2. EXCLUDE: consultancies/agencies, investors/PE funds (unless the TARGET is
   named — then list the target), universities, hospitals-as-buyers, media.
3. One entry per company, keep the url of the finding that mentions it.

Output — strict JSON, nothing else:
{"companies": [{"name": "<exact name>", "url": "<finding url or null>"}]}
Empty is valid: {"companies": []}."""


@dataclass
class Candidate:
    name: str
    theme: str
    url: str | None


# ─────────────────────────────────────────────────────────────────────────────
# Thematic search (live, money-gated)
# ─────────────────────────────────────────────────────────────────────────────

def _exa_theme(cfg: EngineConfig, query: str, num: int = 8) -> list[dict]:
    data = _post_json(
        "https://api.exa.ai/search",
        {"query": query, "numResults": num,
         "contents": {"text": {"maxCharacters": 400}}},
        {"x-api-key": cfg.exa_api_key},
    )
    return [{"title": r.get("title") or "", "url": r.get("url"),
             "snippet": (r.get("text") or "")[:400]}
            for r in data.get("results", [])]


def _serp_theme(cfg: EngineConfig, query: str) -> list[dict]:
    if cfg.serper_api_key:
        data = _post_json("https://google.serper.dev/news",
                          {"q": query, "num": 8},
                          {"X-API-KEY": cfg.serper_api_key})
        items = data.get("news", [])
    else:
        data = _get_json(_serpapi_url("google_news", query, cfg.serpapi_key))
        items = data.get("news_results", [])
    return [{"title": i.get("title") or "", "url": i.get("link"),
             "snippet": i.get("snippet") or ""} for i in items]


def search_themes(cfg: EngineConfig) -> list[tuple[str, dict]]:
    """(theme, finding) pairs across all discovery queries. Live only."""
    require_live(cfg, cfg.exa_api_key or cfg.serpapi_key or cfg.serper_api_key,
                 "Discovery search")
    findings: list[tuple[str, dict]] = []
    for theme, query in DISCOVERY_QUERIES:
        for fn in (_exa_theme, _serp_theme):
            try:
                if fn is _exa_theme and not cfg.exa_api_key:
                    continue
                if fn is _serp_theme and not (cfg.serper_api_key or cfg.serpapi_key):
                    continue
                for f in fn(cfg, query):
                    findings.append((theme, f))
            except Exception as exc:   # one dead source must not kill discovery
                logger.info("[discovery] %s skipped for %r: %s",
                            fn.__name__, query[:40], exc)
    if cfg.exa_api_key:
        from pipeline.usage_log import log_search_calls
        log_search_calls("exa", len(DISCOVERY_QUERIES), "discovery")
    logger.info("[discovery] %d findings across %d themes",
                len(findings), len(DISCOVERY_QUERIES))
    return findings


# ─────────────────────────────────────────────────────────────────────────────
# Name extraction (Sonnet, one small call) + universe filter
# ─────────────────────────────────────────────────────────────────────────────

def _findings_payload(findings: list[tuple[str, dict]]) -> str:
    lines = []
    for theme, f in findings:
        lines.append(f"- [{theme}] {f['title']} | url={f['url'] or 'null'}\n"
                     f"  {f['snippet']}")
    return "\n".join(lines)


# Findings per Sonnet call. One call over 462 findings truncated at max_tokens
# (output hit the cap exactly → unparseable → 0 names). Chunking bounds the
# reply size — the same defense as extraction's CHUNK_DOCS.
CHUNK_FINDINGS = 80


def _parse_companies(text: str) -> list[dict]:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    candidate = m.group() if m else text
    try:
        return json.loads(candidate).get("companies", [])
    except (json.JSONDecodeError, AttributeError):
        # Truncated reply: salvage every complete {"name": ...} object.
        out = []
        for obj in re.finditer(r"\{[^{}]*\}", candidate):
            try:
                d = json.loads(obj.group())
            except json.JSONDecodeError:
                continue
            if isinstance(d, dict) and d.get("name"):
                out.append(d)
        logger.warning("[discovery] broken JSON — salvaged %d complete entries", len(out))
        return out


def extract_candidates(cfg: EngineConfig,
                       findings: list[tuple[str, dict]]) -> list[Candidate]:
    if not findings:
        return []
    require_live(cfg, cfg.anthropic_api_key, "Discovery extraction (Sonnet)")
    import anthropic
    from pipeline.usage_log import log_anthropic_call

    theme_by_url = {f["url"]: theme for theme, f in findings if f["url"]}
    client = anthropic.Anthropic(api_key=cfg.anthropic_api_key)
    out: list[Candidate] = []
    chunks = [findings[i:i + CHUNK_FINDINGS]
              for i in range(0, len(findings), CHUNK_FINDINGS)]
    for n, chunk in enumerate(chunks, 1):
        response = client.messages.create(
            model=cfg.extraction_model,
            max_tokens=8192,
            system=DISCOVER_PROMPT,
            messages=[{"role": "user",
                       "content": f"FINDINGS:\n\n{_findings_payload(chunk)}"}],
        )
        text = "".join(b.text for b in response.content if b.type == "text")
        if response.stop_reason == "max_tokens":
            logger.warning("[discovery] chunk %d/%d hit max_tokens (truncated)",
                           n, len(chunks))
        log_anthropic_call(cfg.extraction_model, response.usage, "discovery", "discover")
        for raw in _parse_companies(text):
            name = (raw.get("name") or "").strip()
            if name:
                url = raw.get("url") or None
                out.append(Candidate(name=name, url=url,
                                     theme=theme_by_url.get(url, "unknown")))
    return out


def _norm(name: str) -> str:
    n = re.sub(r"\(.*?\)", "", name.lower())
    n = re.sub(r"\b(group|holding|ag|sa|sl|gmbh|inc|ltd|llc|europe|international)\b", "", n)
    return re.sub(r"\W+", " ", n).strip()


def filter_new(candidates: list[Candidate],
               known_names: list[str]) -> list[Candidate]:
    """Candidates NOT already in the scored universe (normalised), deduped.
    This is the point of discovery: bring NEW companies, never re-surface last
    month's list."""
    return partition_candidates(candidates, known_names)[0]


def partition_candidates(candidates: list[Candidate], known_names: list[str]
                         ) -> tuple[list[Candidate], list[Candidate]]:
    """Split the watch's findings into (fresh, resurfaced):
      - fresh      = genuinely NEW companies → the discovery output to score.
      - resurfaced = companies ALREADY tracked that reappeared in the watch this
        month → NOT re-scored, but worth flagging ("this account is back in the
        news"). Each deduped within its group."""
    known = {_norm(n) for n in known_names}
    seen_new: set[str] = set()
    seen_old: set[str] = set()
    fresh: list[Candidate] = []
    resurfaced: list[Candidate] = []
    for c in candidates:
        key = _norm(c.name)
        if not key:
            continue
        if key in known:
            if key not in seen_old:
                seen_old.add(key)
                resurfaced.append(c)
        elif key not in seen_new:
            seen_new.add(key)
            fresh.append(c)
    return fresh, resurfaced


def known_universe() -> list[str]:
    """Company names already scored (fail-open: no DB ⇒ empty list)."""
    try:
        from app.database import SessionLocal
        from app.models import Company
        with SessionLocal() as db:
            return [c.name for c in db.query(Company.name).all()]
    except Exception as exc:
        logger.warning("[discovery] universe unavailable (%s) — no dedup", exc)
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

RESURFACED_OUT = Path("data/csv/discovery_resurfaced.csv")


def _write_candidates(rows: list[Candidate], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Company Name", "Theme", "Source URL"])
        for c in rows:
            w.writerow([c.name, c.theme, c.url or ""])


def discover(cfg: EngineConfig, out: Path = DEFAULT_OUT) -> list[Candidate]:
    """Full discovery pass. Writes NEW candidates (to score) to `out`, and the
    already-tracked companies that RESURFACED in the watch to a separate file
    (informational — never auto-scored)."""
    findings = search_themes(cfg)
    candidates = extract_candidates(cfg, findings)
    fresh, resurfaced = partition_candidates(candidates, known_universe())
    _write_candidates(fresh, out)
    _write_candidates(resurfaced, RESURFACED_OUT)
    logger.info("[discovery] %d findings → %d names → %d NEW candidates (%s) + "
                "%d resurfaced/already-tracked (%s)",
                len(findings), len(candidates), len(fresh), out,
                len(resurfaced), RESURFACED_OUT)
    if fresh:
        names = ";".join(c.name for c in fresh[:20])
        logger.info("[discovery] score the NEW ones with:\n"
                    '    python -m pipeline.runner --names "%s" --live --max-usd 5', names)
    if resurfaced:
        logger.info("[discovery] %d existing accounts are back in the news this "
                    "month (flag for Maya, not re-scored): %s", len(resurfaced),
                    ", ".join(c.name for c in resurfaced[:10]))
    return fresh
