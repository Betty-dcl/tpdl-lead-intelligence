"""Web search utility for Iris / marketing content.

Prefers **Serper** (google.serper.dev — the target SERP engine, higher quality)
when SERPER_API_KEY is set, and falls back to **DuckDuckGo** (no key needed) so
the feature keeps working with zero configuration. Same return contract either
way: a list of {title, url/href, body} dicts. Never raises — returns [] on error.
"""
import json
import logging
import urllib.request

from app.config import settings

logger = logging.getLogger(__name__)


def _serper_search(query: str, max_results: int) -> list[dict]:
    """Serper google search → normalised {title, url, href, body} dicts."""
    req = urllib.request.Request(
        "https://google.serper.dev/search",
        data=json.dumps({"q": query, "num": max_results}).encode(),
        headers={"Content-Type": "application/json", "X-API-KEY": settings.serper_api_key},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode())
    out = []
    for item in (data.get("organic") or [])[:max_results]:
        link = item.get("link", "")
        out.append({
            "title": item.get("title", ""),
            "url": link, "href": link,
            "body": item.get("snippet", ""),
        })
    return out


def _ddg_search(query: str, max_results: int) -> list[dict]:
    from duckduckgo_search import DDGS
    with DDGS() as ddgs:
        return list(ddgs.text(query, max_results=max_results)) or []


def search_web(query: str, max_results: int = 5) -> list[dict]:
    """Return [{title, url/href, body}] for the query. Serper if keyed, else DuckDuckGo."""
    engine = _serper_search if settings.serper_api_key else _ddg_search
    try:
        return engine(query, max_results)
    except Exception as exc:
        logger.warning("[web_search] %s query=%r failed: %s",
                       "serper" if settings.serper_api_key else "ddg", query, exc)
        # If Serper errored, try the keyless fallback before giving up.
        if settings.serper_api_key:
            try:
                return _ddg_search(query, max_results)
            except Exception:
                pass
        return []


def build_search_context(subject: str, sector_hint: str = "pharma life sciences") -> str:
    """Run 2-3 targeted queries and return a formatted context block for Marc."""
    queries = [
        f"{subject} {sector_hint} 2024 2025 statistics data",
        f"{subject} trends challenges opportunities",
        f"{subject} case study results impact",
    ]

    blocks = []
    seen_urls: set[str] = set()

    for q in queries:
        results = search_web(q, max_results=3)
        for r in results:
            url = r.get("href") or r.get("url", "")
            if url in seen_urls:
                continue
            seen_urls.add(url)
            title = r.get("title", "").strip()
            body  = r.get("body",  "").strip()
            if title and body:
                blocks.append(f"SOURCE: {title}\nURL: {url}\nEXCERPT: {body[:300]}")

    if not blocks:
        return ""

    header = (
        f"=== REAL-TIME SEARCH RESULTS FOR: {subject} ===\n"
        "Use the facts, stats, and context below to write data-driven content.\n"
        "Cite sources implicitly (e.g. 'recent studies show…'). Never fabricate data.\n\n"
    )
    return header + "\n\n---\n\n".join(blocks[:8])
