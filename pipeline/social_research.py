"""Step 2 (opt-in, 9th source) — social/video research via agent-reach's CLIs.

Free (no metered API key): reuses Betty's own logged-in browser session
(OpenCLI + Chrome) for Twitter/X, Reddit, LinkedIn and Instagram, plus yt-dlp
for YouTube search (zero login needed). Opt-in only (--social-scan /
SOCIAL_SCAN_ENABLED=1): this is browser automation, not an HTTP API — slower
per company and subject to each platform's own rate limits, so it is sized
for a shortlist/--lunch/--names run, not the full 500+-company universe.

Verified live 2026-08-13 against Cantabria Labs: Twitter and Reddit work
(OpenCLI, Betty's Chrome session). Instagram works via the dedicated
giraffe.agent account (github.com/… IG search is user-lookup only, so this
resolves the official/verified account first, then reads its recent posts —
expect near-zero B2B signal yield, these companies post consumer marketing,
not corporate news). YouTube search works zero-config but degrades to
unrelated generic videos for small/private companies — filtered below to
require the company name literally in the text. LinkedIn jobs search
(--company filter, does NOT touch LinkedIn's people-search quota) is wired
in but currently fails on Betty's account with "Text not found: Jobs" — a
UI-automation/locale mismatch in the OpenCLI adapter, not a bug here; fails
open (empty result) like any other source until that's fixed on her side.

Feeds the SAME extract.py (Sonnet 5) → score.py (Opus 4.8) pipeline as every
other source: nothing here interprets or judges, it only returns RawDoc text
for the extractor to isolate verbatim quotes from — same structural
anti-hallucination separation as the rest of the engine.
"""
from __future__ import annotations

import json
import logging
import re
import subprocess
from datetime import date, datetime

from pipeline.config import EngineConfig
from pipeline.types import RawDoc

logger = logging.getLogger(__name__)

_TIMEOUT = 60  # seconds — browser-automation backends are slower than HTTP APIs


def _run_cli(args: list[str]) -> str | None:
    """Fail-open subprocess call: missing binary / timeout / non-zero exit /
    empty output ⇒ None. Never raises — a social source going offline (no
    login, platform UI change, rate limit) must never break a run, same
    contract as every conditional source in research.py."""
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=_TIMEOUT)
    except FileNotFoundError:
        logger.info("[social] %s not installed — skipping", args[0])
        return None
    except subprocess.TimeoutExpired:
        logger.info("[social] %s timed out after %ss", args[0], _TIMEOUT)
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        logger.info("[social] %s exited %s: %s", " ".join(args[:3]), proc.returncode,
                    (proc.stderr or proc.stdout or "")[:200])
        return None
    return proc.stdout


def _run_json(args: list[str]) -> list[dict]:
    raw = _run_cli(args)
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.info("[social] %s returned unparseable JSON", args[0])
        return []
    if isinstance(data, dict):
        if data.get("ok") is False:      # OpenCLI's own error envelope
            logger.info("[social] %s: %s", args[0], data.get("error"))
            return []
        data = data.get("items") or data.get("results") or [data]
    return data if isinstance(data, list) else []


def _mentions(company: str, *texts: str) -> bool:
    """Cheap noise filter: require the company literally in the text before it
    ever reaches the (expensive) extraction step — YouTube search in particular
    degrades to generic unrelated videos for small/private companies."""
    needle = company.strip().lower()
    return bool(needle) and any(needle in (t or "").lower() for t in texts)


def _normalize(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _account_matches(company: str, *fields: str) -> bool:
    """Instagram/handle matching, punctuation/space-insensitive: handles have no
    spaces ("cantabrialabs_esp") and bios often use a product brand instead of
    the legal name ("Heliocare, Endocare y más") — a literal `_mentions` check
    would reject the real official account, as it did on the first live test."""
    needle = _normalize(company)
    return bool(needle) and any(needle in _normalize(f or "") for f in fields)


def _parse_twitter_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%a %b %d %H:%M:%S %z %Y").date()
    except ValueError:
        return None


def _parse_ddmmyyyy(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%d/%m/%Y").date()
    except ValueError:
        return None


def _parse_yt_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y%m%d").date()
    except ValueError:
        return None


# ── Twitter/X (OpenCLI, Betty's Chrome session) ────────────────────────────

def twitter_search(cfg: EngineConfig, company: str) -> list[RawDoc]:
    if not cfg.social_scan_enabled:
        return []
    items = _run_json(["opencli", "twitter", "search", company,
                       "--exclude", "retweets", "--limit", "15", "-f", "json"])
    docs = []
    for it in items:
        text = it.get("text") or ""
        if not _mentions(company, text):
            continue
        docs.append(RawDoc(
            source="twitter", url=it.get("url"),
            title=f"Tweet — @{it.get('author', '?')}",
            text=text, published=_parse_twitter_date(it.get("created_at")),
        ))
    return docs


# ── Reddit (OpenCLI, Betty's Chrome session) ───────────────────────────────

def reddit_search(cfg: EngineConfig, company: str) -> list[RawDoc]:
    if not cfg.social_scan_enabled:
        return []
    items = _run_json(["opencli", "reddit", "search", company,
                       "--time", "year", "--limit", "15", "-f", "json"])
    docs = []
    for it in items:
        title, body = it.get("title") or "", it.get("selftext") or ""
        if not _mentions(company, title, body):
            continue
        created = it.get("created_utc")
        docs.append(RawDoc(
            source="reddit", url=it.get("url"), title=title,
            text=f"{title}\n{body}"[:3000],
            published=date.fromtimestamp(created) if created else None,
        ))
    return docs


# ── LinkedIn jobs (OpenCLI, Betty's Chrome session — the --company filtered
# job search, NOT people-search, so it never touches LinkedIn's monthly
# Commercial-Use-Limit) ─────────────────────────────────────────────────────

def linkedin_jobs(cfg: EngineConfig, company: str) -> list[RawDoc]:
    if not cfg.social_scan_enabled:
        return []
    items = _run_json(["opencli", "linkedin", "search", "commercial OR digital OR CRM OR data",
                       "--company", company, "--limit", "15", "-f", "json"])
    docs = []
    for it in items:
        title = it.get("title") or ""
        if not title:
            continue
        docs.append(RawDoc(
            source="linkedin_jobs", url=it.get("url") or it.get("apply_url"),
            title=f"LinkedIn job — {title}",
            text=(f"{title} at {company}. {it.get('location', '')} "
                 f"{it.get('description', '')}")[:2000],
        ))
    return docs


# ── Instagram (OpenCLI, giraffe.agent account) — search is user-lookup only,
# so resolve the official/verified account first, then read its recent posts.
# ─────────────────────────────────────────────────────────────────────────────

def instagram_posts(cfg: EngineConfig, company: str) -> list[RawDoc]:
    if not cfg.social_scan_enabled:
        return []
    accounts = _run_json(["opencli", "instagram", "search", company, "-f", "json"])
    candidates = [a for a in accounts
                 if _account_matches(company, a.get("name", ""), a.get("username", ""))]
    if not candidates:
        return []
    account = next((a for a in candidates if str(a.get("verified", "")).lower() == "yes"),
                   candidates[0])
    username = account.get("username")
    if not username:
        return []
    posts = _run_json(["opencli", "instagram", "user", username, "--limit", "10", "-f", "json"])
    docs = []
    for p in posts:
        caption = p.get("caption") or ""
        if not caption:
            continue
        docs.append(RawDoc(
            # url=None: OpenCLI exposes no per-post URL, only the profile's —
            # anchors to the account, not the specific post (Perplexity-style:
            # corroborates but doesn't verify a specific claim).
            source="instagram", url=None,
            title=f"Instagram — @{username}",
            text=caption, published=_parse_ddmmyyyy(p.get("date")),
        ))
    return docs


# ── YouTube (yt-dlp, zero config) — filtered: search silently degrades to
# generic unrelated videos once the company has little/no video presence.
# ─────────────────────────────────────────────────────────────────────────────

def youtube_search(cfg: EngineConfig, company: str) -> list[RawDoc]:
    if not cfg.social_scan_enabled:
        return []
    raw = _run_cli(["yt-dlp", "--dump-json", "--flat-playlist", "--playlist-end", "5",
                   f"ytsearch5:{company} earnings OR interview OR CEO OR investment"])
    if not raw:
        return []
    docs = []
    for line in raw.splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        title, desc = item.get("title") or "", item.get("description") or ""
        if not _mentions(company, title, desc):
            continue
        docs.append(RawDoc(
            source="youtube", url=item.get("webpage_url") or item.get("url"),
            title=title, text=desc[:1500],
            published=_parse_yt_date(item.get("upload_date")),
        ))
    return docs


SOURCES = (twitter_search, reddit_search, linkedin_jobs, instagram_posts, youtube_search)
