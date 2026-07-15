"""Research disk cache — the Neotek trick that makes re-scoring free.

Research (step 2) is the expensive step. Once a company's raw docs are on
disk, steps 3-4 can be re-run (new prompts, new weights) without paying for
a single new search. Cache lives under data/cache/research/, one JSON per
company, with a fetched_at stamp and a max-age guard.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path

from pipeline.types import RawDoc

CACHE_DIR = Path("data/cache/research")
DEFAULT_MAX_AGE_DAYS = 7


def _slug(company: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", company.lower()).strip("-") or "company"


def cache_path(company: str, cache_dir: Path = CACHE_DIR) -> Path:
    return cache_dir / f"{_slug(company)}.json"


def save(company: str, docs: list[RawDoc], cache_dir: Path = CACHE_DIR) -> Path:
    path = cache_path(company, cache_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "company": company,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "docs": [
            {"source": d.source, "url": d.url, "title": d.title, "text": d.text,
             "published": d.published.isoformat() if d.published else None}
            for d in docs
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def load(company: str, cache_dir: Path = CACHE_DIR,
         max_age_days: int = DEFAULT_MAX_AGE_DAYS) -> list[RawDoc] | None:
    """Return cached docs, or None when absent/stale."""
    path = cache_path(company, cache_dir)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        fetched = datetime.fromisoformat(payload["fetched_at"])
    except (json.JSONDecodeError, KeyError, ValueError):
        return None
    age = datetime.now(timezone.utc) - fetched
    if age.days >= max_age_days:
        return None
    return [
        RawDoc(
            source=d.get("source", "cache"),
            url=d.get("url"),
            title=d.get("title", ""),
            text=d.get("text", ""),
            published=date.fromisoformat(d["published"]) if d.get("published") else None,
        )
        for d in payload.get("docs", [])
    ]
