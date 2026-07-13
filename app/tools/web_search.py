"""Web search utility — DuckDuckGo, no API key required.

Used by the Carousel Studio to fetch real data before Marc writes.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def search_web(query: str, max_results: int = 5) -> list[dict]:
    """Return a list of {title, url, body} dicts for the query."""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        return results or []
    except Exception as exc:
        logger.warning("[web_search] query=%r failed: %s", query, exc)
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
