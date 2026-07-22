"""Revenue enrichment (opt-in, --enrich-revenue).

For a company whose revenue is unknown, ask Perplexity once for an annual-revenue
figure so the €100M ICP floor (app/tools/icp.py) can actually triage it. Purely
FAIL-OPEN: any error, dry-run, missing key, or unparseable answer → None, and the
revenue simply stays unknown (the company is kept, as before). It can never break
a run. The parser is deterministic and unit-tested; only the network call is live.
"""
from __future__ import annotations

import re

from pipeline.config import EngineConfig

_MULT = {
    "k": 0.001, "thousand": 0.001,
    "m": 1.0, "mm": 1.0, "million": 1.0, "millions": 1.0, "mn": 1.0,
    "b": 1000.0, "bn": 1000.0, "billion": 1000.0, "billions": 1000.0,
}
_CUR = {"€": "€", "eur": "€", "euro": "€", "euros": "€",
        "$": "$", "usd": "$", "dollar": "$", "dollars": "$",
        "£": "£", "gbp": "£", "chf": "CHF", "fr": "CHF"}


def parse_revenue(text: str | None) -> str | None:
    """First plausible annual-revenue figure in free text → a normalised label in
    millions (e.g. '~€250M (estimated)' / '~$1.2B (estimated)'), or None."""
    if not text:
        return None
    low = text.lower().replace(",", "")
    m = re.search(
        r"(€|\$|£|eur|usd|gbp|chf)?\s*([0-9]+(?:\.[0-9]+)?)\s*"
        r"(billion|billions|million|millions|thousand|bn|mn|mm|b|m|k)\b",
        low,
    )
    if not m:
        return None
    cur_raw, num_raw, mult_raw = m.group(1), m.group(2), m.group(3)
    try:
        millions = float(num_raw) * _MULT.get(mult_raw, 1.0)
    except ValueError:
        return None
    if millions <= 0:
        return None
    cur = _CUR.get((cur_raw or "").strip(), "€")
    if millions >= 1000:
        return f"~{cur}{millions / 1000:.1f}B (estimated)"
    return f"~{cur}{millions:.0f}M (estimated)"


def estimate_revenue(cfg: EngineConfig, company: str) -> str | None:
    """One Perplexity call for a company's annual revenue. Fail-open → str|None."""
    try:
        from pipeline.config import require_live
        require_live(cfg, cfg.perplexity_api_key, "revenue enrichment")
    except Exception:
        return None
    try:
        from pipeline.research import _post_json
        from pipeline.usage_log import log_search_calls
        log_search_calls("perplexity", 1, company)
        data = _post_json(
            "https://api.perplexity.ai/chat/completions",
            {"model": "sonar", "messages": [{
                "role": "user",
                "content": (
                    f"What is the approximate most recent ANNUAL REVENUE of the "
                    f"company \"{company}\"? Reply with just the figure and currency "
                    f"(e.g. '€250 million' or '$1.2 billion'). If genuinely unknown, "
                    f"reply 'unknown'."
                ),
            }]},
            {"Authorization": f"Bearer {cfg.perplexity_api_key}"},
        )
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not text or "unknown" in text.lower():
            return None
        return parse_revenue(text)
    except Exception:
        return None
