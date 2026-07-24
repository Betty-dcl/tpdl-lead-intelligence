"""Step 2 — Research: the source clients that feed raw documents to extraction.

Every live client funnels through `require_live()` (the single money gate):
in dry-run mode nothing here can touch the network or cost a cent.

Target stack (design): Exa Q1/Q2/Q3, Perplexity Sonar (no URLs ⇒ corroboration 0),
Serper News + Jobs (replaces SerpAPI), EU registries (conditional),
IR page fetch via Firecrawl (conditional).
"""
from __future__ import annotations

import json
import logging
import re
import time
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path

from pipeline.config import EngineConfig, require_live
from pipeline.types import RawDoc

logger = logging.getLogger(__name__)

_TIMEOUT = 30       # seconds
_RETRIES = 3        # attempts per call
_BACKOFF = 1.5      # seconds, doubled each retry


def _urlopen_json(url: str, payload: dict, headers: dict) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read().decode())


def _urlopen_get_json(url: str) -> dict:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read().decode())


def _with_retry(fn, *args, what: str = "request"):
    """Retry + exponential backoff on transient failures (429/5xx/network)."""
    delay = _BACKOFF
    for attempt in range(1, _RETRIES + 1):
        try:
            return fn(*args)
        except urllib.error.HTTPError as exc:
            transient = exc.code == 429 or exc.code >= 500
            if not transient or attempt == _RETRIES:
                raise
            logger.info("[research] HTTP %s (%s) — retry %d/%d in %.1fs",
                        exc.code, what, attempt, _RETRIES, delay)
        except urllib.error.URLError as exc:
            if attempt == _RETRIES:
                raise
            logger.info("[research] network error (%s, %s) — retry %d/%d in %.1fs",
                        exc.reason, what, attempt, _RETRIES, delay)
        time.sleep(delay)
        delay *= 2
    raise RuntimeError("unreachable")


def _post_json(url: str, payload: dict, headers: dict) -> dict:
    return _with_retry(_urlopen_json, url, payload, headers, what=url)


def _get_json(url: str) -> dict:
    return _with_retry(_urlopen_get_json, url, what=url.split("?")[0])


def dedupe(docs: list[RawDoc]) -> list[RawDoc]:
    """Drop duplicate documents: same URL, or same normalised title.

    Two engines returning the same article must not count twice — neither in
    evidence volume nor (later) in corroboration.
    """
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    unique: list[RawDoc] = []
    for d in docs:
        url_key = (d.url or "").rstrip("/").lower()
        title_key = re.sub(r"\W+", " ", d.title).strip().lower()
        if url_key and url_key in seen_urls:
            continue
        if title_key and title_key in seen_titles:
            continue
        if url_key:
            seen_urls.add(url_key)
        if title_key:
            seen_titles.add(title_key)
        unique.append(d)
    return unique


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    s = value.strip()
    # ISO first, then SerpAPI's US format (MM/DD/YYYY) — the news engines emit
    # the latter, so without it every SERP-sourced doc lost its recency points.
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d",
                "%m/%d/%Y", "%b %d, %Y", "%d %b %Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    # Relative form ("2 days ago", "3 weeks ago") — Serper's news date field.
    return _parse_relative_date(s)


def _parse_relative_date(s: str, today: date | None = None) -> date | None:
    m = re.match(r"(\d+)\s+(day|week|month|year)s?\s+ago", s.lower())
    if not m:
        return None
    from datetime import timedelta
    n, unit = int(m.group(1)), m.group(2)
    days = {"day": 1, "week": 7, "month": 30, "year": 365}[unit] * n
    return (today or date.today()) - timedelta(days=days)


# ─────────────────────────────────────────────────────────────────────────────
# Serper (target SERP engine — replaces SerpAPI)
# ─────────────────────────────────────────────────────────────────────────────

# SERP locale per company, derived from its known location (Europe-first:
# CH + ES are the reference/Lunch markets). A Swiss company's news is searched
# with gl=ch, a Spanish one with gl=es — better regional/trade-press ranking
# WITHOUT adding any extra search (same 2 SERP calls/company, just localised).
# Unknown or non-European location ⇒ (None, None) = global (unchanged behaviour).
# hl left None where a country is multilingual (CH); the multilingual extraction
# already handles FR/DE/IT, so gl alone is enough there.
_MARKET_LOCALE: dict[str, tuple[str, str | None]] = {
    "CH": ("ch", None), "ES": ("es", "es"), "FR": ("fr", "fr"),
    "DE": ("de", "de"), "IT": ("it", "it"), "GB": ("uk", "en"),
    "UK": ("uk", "en"), "BE": ("be", None), "NL": ("nl", "nl"),
    "AT": ("at", "de"), "PT": ("pt", "pt"), "IE": ("ie", "en"),
    "SE": ("se", "sv"), "DK": ("dk", "da"), "NO": ("no", "no"),
    "FI": ("fi", "fi"), "GR": ("gr", "el"),
    # Middle East (phase 2 — in scope)
    "AE": ("ae", "en"), "SA": ("sa", "ar"), "EG": ("eg", "ar"),
    "IL": ("il", "he"), "TR": ("tr", "tr"), "QA": ("qa", "en"),
}


def _market_locale(location: str | None) -> tuple[str | None, str | None]:
    """(gl, hl) for a company location, or (None, None) if unknown. Uses the
    broad market-country detector so FR/DE/IT/Nordics/Middle East localise too,
    not just CH/ES."""
    if not location:
        return (None, None)
    try:
        from app.tools.radars import detect_market_country
        return _MARKET_LOCALE.get(detect_market_country(location) or "", (None, None))
    except Exception:
        return (None, None)


def serper_news(cfg: EngineConfig, company: str, num: int = 10,
                gl: str | None = None, hl: str | None = None) -> list[RawDoc]:
    """Serper Google News — regional/trade press. https://serper.dev"""
    require_live(cfg, cfg.serper_api_key, "Serper News")
    payload = {"q": f'"{company}"', "num": num}
    if gl:
        payload["gl"] = gl
    if hl:
        payload["hl"] = hl
    data = _post_json(
        "https://google.serper.dev/news",
        payload,
        {"X-API-KEY": cfg.serper_api_key},
    )
    return [
        RawDoc(
            source="serper_news",
            url=item.get("link"),
            title=item.get("title", ""),
            text=item.get("snippet", ""),
            published=_parse_date(item.get("date")),
        )
        for item in data.get("news", [])
    ]


# Hiring intent across the target markets (EN/FR/ES/DE). A French or Spanish job
# posting never says "hiring"/"careers", so an English-only query silently misses
# European recruitment signals. The role focus (commercial/digital/CRM/data) stays
# in its already-international form. No country locale (gl/hl) is hardcoded here:
# the market geography is still an open scope question (see the segmentation draft),
# so we widen the LANGUAGE of the query, not its country.
_HIRING_TERMS = ("hiring OR jobs OR careers OR emploi OR recrutement OR carrières "
                 "OR empleo OR contratación OR empleos OR Karriere OR Stellenangebote")


def _jobs_query(company: str) -> str:
    """SERP query for hiring signals — exposed as a pure function so it is testable
    without a live call."""
    return f'"{company}" ({_HIRING_TERMS}) commercial digital CRM'


def serper_jobs(cfg: EngineConfig, company: str, num: int = 10,
                gl: str | None = None, hl: str | None = None) -> list[RawDoc]:
    """Serper Google search scoped to job postings — direct hiring-signal proxy."""
    require_live(cfg, cfg.serper_api_key, "Serper Jobs")
    payload = {"q": _jobs_query(company), "num": num}
    if gl:
        payload["gl"] = gl
    if hl:
        payload["hl"] = hl
    data = _post_json(
        "https://google.serper.dev/search",
        payload,
        {"X-API-KEY": cfg.serper_api_key},
    )
    return [
        RawDoc(
            source="serper_jobs",
            url=item.get("link"),
            title=item.get("title", ""),
            text=item.get("snippet", ""),
        )
        for item in data.get("organic", [])
    ]


# ─────────────────────────────────────────────────────────────────────────────
# SerpAPI — transition SERP engine (we already pay for it; Serper stays the
# target once subscribed — gather() prefers Serper automatically when its key
# lands in .env, no code change needed).
# ─────────────────────────────────────────────────────────────────────────────

def _serpapi_url(engine: str, query: str, key: str,
                 gl: str | None = None, hl: str | None = None) -> str:
    from urllib.parse import urlencode
    params = {"engine": engine, "q": query, "api_key": key}
    if gl:
        params["gl"] = gl
    if hl:
        params["hl"] = hl
    return "https://serpapi.com/search.json?" + urlencode(params)


class SerpApiExhausted(Exception):
    """SerpAPI has no searches left this billing cycle. Signals the SERP layer
    to stop calling SerpAPI and switch to the Serper backup for the rest of the
    run (Betty's strategy: drain the SerpAPI subscription, then fall back)."""


# SerpAPI returns HTTP 200 with an {"error": ...} body when the account is out
# of searches — so a naive parse would look like "no results". These markers let
# us tell "quota gone" apart from a genuine empty result.
_SERPAPI_QUOTA_MARKERS = (
    "run out of searches", "ran out of searches", "out of searches",
    "no more searches", "exceeded your", "account limit", "plan searches",
    "monthly searches", "search limit",
)


def _check_serpapi_quota(data: dict) -> dict:
    """Raise SerpApiExhausted if the SerpAPI body signals a depleted quota."""
    err = str(data.get("error") or "").lower()
    if err and any(m in err for m in _SERPAPI_QUOTA_MARKERS):
        raise SerpApiExhausted(data.get("error"))
    return data


def serpapi_news(cfg: EngineConfig, company: str,
                 gl: str | None = None, hl: str | None = None) -> list[RawDoc]:
    """SerpAPI Google News — same role as serper_news."""
    require_live(cfg, cfg.serpapi_key, "SerpAPI News")
    data = _check_serpapi_quota(
        _get_json(_serpapi_url("google_news", f'"{company}"', cfg.serpapi_key, gl, hl)))
    return [
        RawDoc(
            source="serpapi_news",
            url=item.get("link"),
            title=item.get("title", ""),
            text=item.get("snippet", "") or item.get("title", ""),
            published=_parse_date(item.get("date", "").split(",")[0].strip() or None),
        )
        for item in data.get("news_results", [])
    ]


def serpapi_jobs(cfg: EngineConfig, company: str,
                 gl: str | None = None, hl: str | None = None) -> list[RawDoc]:
    """SerpAPI Google Jobs — direct hiring-signal proxy (same role as serper_jobs)."""
    require_live(cfg, cfg.serpapi_key, "SerpAPI Jobs")
    data = _check_serpapi_quota(_get_json(_serpapi_url(
        "google_jobs", f"{company} commercial digital CRM data", cfg.serpapi_key, gl, hl)))
    docs = []
    for item in data.get("jobs_results", []):
        # Only keep postings actually at the target company
        if company.lower() not in (item.get("company_name", "") or "").lower():
            continue
        docs.append(RawDoc(
            source="serpapi_jobs",
            url=item.get("share_link"),
            title=item.get("title", ""),
            text=(item.get("description", "") or "")[:2000],
        ))
    return docs


# ── SERP with SerpAPI→Serper fallback (drain SerpAPI, then use the backup) ────

def serpapi_exhausted(cfg: EngineConfig) -> bool:
    """Run-scoped flag: True once SerpAPI reported no searches left this run."""
    return bool(getattr(cfg, "_serpapi_exhausted", False))


def _serp_with_fallback(cfg: EngineConfig, kind: str, company: str,
                        gl: str | None, hl: str | None) -> list[RawDoc]:
    """Try SerpAPI first (drain the current subscription); on quota-exhaustion
    switch permanently to Serper for the rest of the run; on a transient SerpAPI
    error fall back to Serper for THIS company only (keep trying SerpAPI next).
    Never raises for a SERP failure — worst case returns []."""
    serpapi_fn = serpapi_news if kind == "news" else serpapi_jobs
    serper_fn = serper_news if kind == "news" else serper_jobs

    if cfg.serpapi_key and not serpapi_exhausted(cfg):
        try:
            return serpapi_fn(cfg, company, gl=gl, hl=hl)
        except SerpApiExhausted as exc:
            setattr(cfg, "_serpapi_exhausted", True)
            logger.warning("[research] SerpAPI out of searches (%s) — switching to "
                           "the Serper backup for the rest of the run", exc)
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 429):        # auth/quota walls → treat as exhausted
                setattr(cfg, "_serpapi_exhausted", True)
                logger.warning("[research] SerpAPI HTTP %s — treating as exhausted, "
                               "switching to the Serper backup", exc.code)
            else:
                logger.info("[research] SerpAPI %s HTTP %s — trying Serper backup "
                            "for %s", kind, exc.code, company)
        except Exception as exc:              # transient: this company falls back only
            logger.info("[research] SerpAPI %s failed (%s) — trying Serper backup "
                        "for %s", kind, exc, company)

    if cfg.serper_api_key:
        try:
            return serper_fn(cfg, company, gl=gl, hl=hl)
        except Exception as exc:
            logger.info("[research] Serper %s also failed (%s) for %s",
                        kind, exc, company)
    return []


def serp_news(cfg: EngineConfig, company: str,
              gl: str | None = None, hl: str | None = None) -> list[RawDoc]:
    return _serp_with_fallback(cfg, "news", company, gl, hl)


def serp_jobs(cfg: EngineConfig, company: str,
              gl: str | None = None, hl: str | None = None) -> list[RawDoc]:
    return _serp_with_fallback(cfg, "jobs", company, gl, hl)


# ─────────────────────────────────────────────────────────────────────────────
# Exa — neural search, 3 query families (Q1 news / Q2 leadership / Q3 M&A)
# ─────────────────────────────────────────────────────────────────────────────

_EXA_QUERIES = {
    "exa_q1": "{company} recent company news announcement",
    "exa_q2": "{company} new CEO leadership appointment executive hiring",
    "exa_q3": "{company} acquisition merger expansion investment",
}


def exa_search(cfg: EngineConfig, company: str, num: int = 5) -> list[RawDoc]:
    """Exa neural search — finds semantically close, not keyword-matched."""
    require_live(cfg, cfg.exa_api_key, "Exa")
    docs: list[RawDoc] = []
    done = 0
    try:
        for source, template in _EXA_QUERIES.items():
            data = _post_json(
                "https://api.exa.ai/search",
                {
                    "query": template.format(company=company),
                    "numResults": num,
                    "contents": {"text": {"maxCharacters": 2000}},
                },
                {"x-api-key": cfg.exa_api_key},
            )
            done += 1
            for item in data.get("results", []):
                docs.append(RawDoc(
                    source=source,
                    url=item.get("url"),
                    title=item.get("title") or "",
                    text=(item.get("text") or ""),
                    published=_parse_date(item.get("publishedDate")),
                ))
    finally:
        # Exa has no public usage API — the engine keeps its own count
        # (finally: a run aborted mid-loop still records what was spent).
        from pipeline.usage_log import log_search_calls
        log_search_calls("exa", done, company)
    return docs


# ─────────────────────────────────────────────────────────────────────────────
# Perplexity Sonar — financial press. Returns NO stable URLs ⇒ any signal
# corroborated ONLY by Perplexity gets corroboration = 0 (design rule).
# ─────────────────────────────────────────────────────────────────────────────

def perplexity_sonar(cfg: EngineConfig, company: str) -> list[RawDoc]:
    require_live(cfg, cfg.perplexity_api_key, "Perplexity Sonar")
    from pipeline.usage_log import log_search_calls
    log_search_calls("perplexity", 1, company)
    data = _post_json(
        "https://api.perplexity.ai/chat/completions",
        {
            "model": "sonar",
            "messages": [{
                "role": "user",
                "content": (
                    f"Recent private-equity, M&A, leadership or restructuring news "
                    f"about {company}. Report only dated facts from the financial "
                    f"press (Reuters, FT, Bloomberg). If none, say 'none found'."
                ),
            }],
        },
        {"Authorization": f"Bearer {cfg.perplexity_api_key}"},
    )
    text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    if not text or "none found" in text.lower():
        return []
    # url=None on purpose: Perplexity corroborates but never anchors.
    return [RawDoc(source="perplexity", url=None, title=f"Perplexity Sonar — {company}", text=text)]


# ─────────────────────────────────────────────────────────────────────────────
# EU company registries (conditional, FREE) — ownership & director changes for
# private companies without a stock listing. Neotek's tech stack had NO paid
# registry API; the "EU registry" source was public-web based. So we do the same:
# query the PUBLIC registry portals through the SERP engine we already pay for
# (SerpAPI/Serper), keeping only results from real registry domains. Zero new cost.
# Opt-in (eu_registry_enabled) so it doesn't silently eat the SERP quota per run.
# ─────────────────────────────────────────────────────────────────────────────

# Public company-register domains (official portals + open aggregators).
_REGISTRY_DOMAINS = (
    "e-justice.europa.eu",          # official EU Business Registers (BRIS)
    "opencorporates.com",           # open aggregator of national registers
    "find-and-update.company-information.service.gov.uk",  # UK Companies House
    "handelsregister.de", "kvk.nl", "companieshouse.gov.uk",
    "registre-commerce", "registro", "registre",
)


def eu_registry(cfg: EngineConfig, company: str) -> list[RawDoc]:
    require_live(cfg, cfg.serper_api_key or cfg.serpapi_key,
                 "EU registry (public web search)")
    q = (f'"{company}" (company register OR directors OR shareholders OR ownership '
         f'OR "registre du commerce" OR Handelsregister)')
    items: list[tuple] = []
    # Same fallback order as the news/jobs SERP: drain SerpAPI, then Serper.
    if cfg.serpapi_key and not serpapi_exhausted(cfg):
        try:
            data = _check_serpapi_quota(_get_json(_serpapi_url("google", q, cfg.serpapi_key)))
            items = [(i.get("title", ""), i.get("link"), i.get("snippet", ""))
                     for i in data.get("organic_results", [])]
        except SerpApiExhausted as exc:
            setattr(cfg, "_serpapi_exhausted", True)
            logger.warning("[research] SerpAPI out of searches (%s) — EU registry "
                           "falling back to Serper", exc)
        except Exception as exc:
            logger.info("[research] SerpAPI EU-registry failed (%s) — trying Serper", exc)
    if not items and cfg.serper_api_key:
        try:
            data = _post_json("https://google.serper.dev/search", {"q": q, "num": 8},
                              {"X-API-KEY": cfg.serper_api_key})
            items = [(i.get("title", ""), i.get("link"), i.get("snippet", ""))
                     for i in data.get("organic", [])]
        except Exception as exc:
            logger.info("[research] Serper EU-registry also failed (%s)", exc)
    docs: list[RawDoc] = []
    for title, link, snippet in items:
        if link and any(d in link.lower() for d in _REGISTRY_DOMAINS) and snippet:
            docs.append(RawDoc(source="eu_registry", url=link,
                               title=title or f"Registry — {company}", text=snippet))
    return docs


# ─────────────────────────────────────────────────────────────────────────────
# Firecrawl — IR page fetch (conditional step)
# ─────────────────────────────────────────────────────────────────────────────

def firecrawl_fetch(cfg: EngineConfig, url: str) -> list[RawDoc]:
    require_live(cfg, cfg.firecrawl_api_key, "Firecrawl")
    data = _post_json(
        "https://api.firecrawl.dev/v2/scrape",
        {"url": url, "formats": ["markdown"]},
        {"Authorization": f"Bearer {cfg.firecrawl_api_key}"},
    )
    md = (data.get("data") or {}).get("markdown", "")
    if not md:
        return []
    return [RawDoc(source="ir_fetch", url=url, title=f"IR page — {url}", text=md[:20000])]


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures — the dry-run source (zero network, zero cost)
# ─────────────────────────────────────────────────────────────────────────────

def fixture_docs(path: Path) -> list[RawDoc]:
    """Load raw docs from a local JSON fixture (see pipeline/fixtures/)."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [
        RawDoc(
            source=d.get("source", "fixture"),
            url=d.get("url"),
            title=d.get("title", ""),
            text=d["text"],
            published=_parse_date(d.get("published")),
        )
        for d in payload["docs"]
    ]


def gather(cfg: EngineConfig, company: str,
           fixture: Path | None = None,
           use_cache: bool = True,
           location: str | None = None,
           website: str | None = None) -> list[RawDoc]:
    """Run every available source; skip cleanly what is offline.

    Dry-run + no fixture ⇒ empty research (valid: company scores 0).
    Live results are cached on disk (data/cache/research/) so steps 3-4 can
    be re-run — new prompts, new weights — without re-paying for research.
    """
    if fixture is not None:
        return dedupe(fixture_docs(fixture))

    from pipeline import cache as research_cache

    if use_cache:
        cached = research_cache.load(company)
        if cached is not None:
            logger.info("[research] %s: %d docs from cache (no API spend)",
                        company, len(cached))
            return dedupe(cached)

    # SERP engine strategy (Betty, 2026-07-23): DRAIN the existing SerpAPI
    # subscription first, then fall back to the (token-filled) Serper backup once
    # SerpAPI is out — both keys live at once, run never crashes on quota. The
    # two wrappers below carry that fallback; the run-scoped exhaustion flag lives
    # on cfg so once SerpAPI is dry it stops being called for the rest of the run.
    serp_sources = (serp_news, serp_jobs)
    sources = [*serp_sources, exa_search, perplexity_sonar]
    if cfg.eu_registry_enabled:           # conditional free source, opt-in (saves SERP quota)
        sources.append(eu_registry)

    # Conditional IR fetch (design source #8): when the company website is
    # known and the Firecrawl key is present, scrape the site (markdown) —
    # press releases / investor-relations headlines feed the earnings-call
    # angle. One scrape = one Firecrawl credit per company.
    ir_url = None
    if cfg.firecrawl_api_key and website:
        ir_url = website if website.startswith("http") else f"https://{website}"

    # Europe-first locale: SERP sources get the company's market (gl/hl); the
    # neural/registry sources are locale-agnostic and take (cfg, company) only.
    gl, hl = _market_locale(location)
    serp_set = set(serp_sources)

    if ir_url:
        def _ir_source(c, _company, url=ir_url):
            return firecrawl_fetch(c, url)
        _ir_source.__name__ = "firecrawl_ir"
        sources.append(_ir_source)

    docs: list[RawDoc] = []
    for fn in sources:
        try:
            got = fn(cfg, company, gl=gl, hl=hl) if fn in serp_set else fn(cfg, company)
            # Parse-bug canary: a LIVE source returning nothing may be a schema
            # mismatch, not a true absence of signal — make it visible.
            if cfg.live and not got:
                logger.info("[research] %s returned 0 docs for %s "
                            "(real absence, or a parsing/schema issue?)",
                            fn.__name__, company)
            docs.extend(got)
        except Exception as exc:  # EngineOffline or network error: skip, never crash
            logger.info("[research] %s skipped: %s", fn.__name__, exc)

    docs = dedupe(docs)
    if docs and cfg.live:  # only cache real research, never empty dry-runs
        research_cache.save(company, docs)
    return docs
