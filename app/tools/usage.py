"""Subscription usage & credits — one panel per provider.

Providers with a FREE account/usage endpoint (no credit consumed):
    SerpAPI   GET https://serpapi.com/account
    Apify     GET https://api.apify.com/v2/users/me/limits
    Firecrawl GET https://api.firecrawl.dev/v2/team/credit-usage

Anthropic exposes no usage endpoint to standard API keys (Admin key only),
so its panel is a LOCAL tally: every agent call already logs input/output
tokens into activity_log — we sum them and estimate cost at list price.

Exa & Perplexity publish no usage API: shown as "configured" with a
dashboard link. All calls have a hard timeout and degrade to an error
card — this page must never break the dashboard.
"""
from __future__ import annotations

import json
import logging
import time
import urllib.request
from urllib.parse import urlencode

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models import ActivityLog

logger = logging.getLogger(__name__)

_TIMEOUT = 8  # seconds — a slow provider must not hang the page

# List prices (USD per MTok, in/out) — for the local cost estimate only.
# Rows log their `model`; costing everything at Opus price would overstate the
# engine's Sonnet 5 extraction spend by ~2.5×.
_OPUS_IN_PER_MTOK = 5.0
_OPUS_OUT_PER_MTOK = 25.0
_MODEL_PRICES: tuple[tuple[str, float, float], ...] = (
    ("opus", 5.0, 25.0),      # Opus 4.8
    ("sonnet", 2.0, 10.0),    # Sonnet 5 launch pricing (until 2026-08-31, then 3/15)
    ("haiku", 1.0, 5.0),      # legacy safety net
)


def _price(model: str | None) -> tuple[float, float]:
    """(in, out) USD/MTok for a logged model id; unknown/absent ⇒ Opus (agents' default)."""
    low = (model or "").lower()
    for key, p_in, p_out in _MODEL_PRICES:
        if key in low:
            return p_in, p_out
    return _OPUS_IN_PER_MTOK, _OPUS_OUT_PER_MTOK

# ── tiny in-memory TTL cache (provider endpoints shouldn't be hammered) ──
_CACHE: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 120  # seconds


def _cached(key: str, fn):
    now = time.time()
    hit = _CACHE.get(key)
    if hit and now - hit[0] < _CACHE_TTL:
        return hit[1]
    value = fn()
    _CACHE[key] = (now, value)
    return value


def _get_json(url: str, headers: dict | None = None) -> dict:
    req = urllib.request.Request(url, headers=headers or {}, method="GET")
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read().decode())


def _panel(provider: str, label: str, **kw) -> dict:
    """Normalised card shape consumed by the frontend."""
    return {
        "provider": provider,
        "label": label,
        "configured": kw.get("configured", True),
        "ok": kw.get("ok", True),
        "error": kw.get("error"),
        "plan": kw.get("plan"),
        "used": kw.get("used"),
        "limit": kw.get("limit"),
        "remaining": kw.get("remaining"),
        "unit": kw.get("unit", ""),
        "detail": kw.get("detail"),
        "dashboard_url": kw.get("dashboard_url"),
        "role": kw.get("role", ""),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Providers
# ─────────────────────────────────────────────────────────────────────────────

def serpapi_panel() -> dict:
    base = dict(provider="serpapi", label="SerpAPI",
                role="Pipeline SERP engine (News + Jobs) — transitioning to Serper",
                dashboard_url="https://serpapi.com/dashboard")
    if not settings.serpapi_key:
        return _panel(**base, configured=False, ok=False)
    try:
        data = _get_json("https://serpapi.com/account?"
                         + urlencode({"api_key": settings.serpapi_key}))
        limit = data.get("searches_per_month")
        used = data.get("this_month_usage")
        left = data.get("plan_searches_left", data.get("total_searches_left"))
        return _panel(**base, plan=data.get("plan_name") or data.get("plan_id"),
                      used=used, limit=limit, remaining=left, unit="searches / month",
                      detail=f"Account: {data.get('account_email', '—')}")
    except Exception as exc:
        logger.warning("[usage] serpapi: %s", exc)
        return _panel(**base, ok=False, error=str(exc)[:160])


def apify_panel() -> dict:
    base = dict(provider="apify", label="Apify",
                role="Tech scan (Wappalyzer) — engine Step 1",
                dashboard_url="https://console.apify.com/billing")
    if not settings.apify_token:
        return _panel(**base, configured=False, ok=False)
    try:
        data = _get_json("https://api.apify.com/v2/users/me/limits?"
                         + urlencode({"token": settings.apify_token}))
        d = data.get("data", {})
        limits, current = d.get("limits", {}), d.get("current", {})
        limit = limits.get("maxMonthlyUsageUsd")
        used = current.get("monthlyUsageUsd")
        remaining = (round(limit - used, 2)
                     if isinstance(limit, (int, float)) and isinstance(used, (int, float))
                     else None)
        return _panel(**base, plan=d.get("monthlyUsageCycle", {}).get("startAt", "")
                      and "Monthly cycle" or None,
                      used=used, limit=limit, remaining=remaining, unit="USD / month")
    except Exception as exc:
        logger.warning("[usage] apify: %s", exc)
        return _panel(**base, ok=False, error=str(exc)[:160])


def firecrawl_panel() -> dict:
    base = dict(provider="firecrawl", label="Firecrawl",
                role="IR / website page fetch — conditional Step 2",
                dashboard_url="https://www.firecrawl.dev/app")
    key = settings.firecrawl_api_key
    if not key:
        return _panel(**base, configured=False, ok=False)
    try:
        data = _get_json("https://api.firecrawl.dev/v2/team/credit-usage",
                         headers={"Authorization": f"Bearer {key}"})
        d = data.get("data", data)
        remaining = d.get("remainingCredits", d.get("remaining_credits"))
        plan = d.get("planCredits", d.get("plan_credits"))
        used = (plan - remaining) if isinstance(plan, (int, float)) and \
            isinstance(remaining, (int, float)) else None
        return _panel(**base, used=used, limit=plan, remaining=remaining,
                      unit="credits")
    except Exception as exc:
        logger.warning("[usage] firecrawl: %s", exc)
        return _panel(**base, ok=False, error=str(exc)[:160])


def _local_search_tally(db: Session, provider: str) -> tuple[int, int]:
    """(all-time, this-month) request counts the ENGINE logged for a provider
    that has no public usage API (Exa / Perplexity)."""
    from datetime import datetime
    total = month = 0
    month_start = datetime.utcnow().replace(day=1, hour=0, minute=0,
                                            second=0, microsecond=0)
    rows = (db.query(ActivityLog.activity_metadata, ActivityLog.created_at)
            .filter(ActivityLog.action == "engine_search").all())
    for meta, created in rows:
        try:
            data = json.loads(meta)
        except (TypeError, json.JSONDecodeError):
            continue
        if data.get("provider") != provider:
            continue
        n = int(data.get("requests", 0) or 0)
        total += n
        if created and created >= month_start:
            month += n
    return total, month


# Rough list price per request, USD — ONLY for the local spend ESTIMATE on
# providers with no usage API. Real balances live on each dashboard.
_SEARCH_UNIT_USD = {"exa": 0.005, "perplexity": 0.005, "serper": 0.001}


def _search_detail(db: Session, provider: str, fallback: str) -> str:
    try:
        total, month = _local_search_tally(db, provider)
    except Exception:                      # tally must never break the page
        return fallback
    if not total:
        return fallback + " Local engine count: 0 requests logged so far."
    unit = _SEARCH_UNIT_USD.get(provider, 0)
    est = f" · est. spend ~${total * unit:.2f} all-time (rough, list price)" if unit else ""
    return (f"Local engine count: {month} requests this month · {total} all-time"
            f"{est} (counted by the engine — no public usage API; exact balance on "
            f"the provider dashboard).")


def exa_panel(db: Session) -> dict:
    return _panel(
        provider="exa", label="Exa",
        role="Neural search ×3 (news / leadership / M&A) — engine Step 2",
        configured=bool(settings.exa_api_key),
        ok=bool(settings.exa_api_key),
        detail=_search_detail(db, "exa",
                              "No public usage API — balance lives on the Exa dashboard."),
        dashboard_url="https://dashboard.exa.ai")


def perplexity_panel(db: Session) -> dict:
    return _panel(
        provider="perplexity", label="Perplexity",
        role="Sonar, financial press PE/M&A — corroborates, never anchors",
        configured=bool(settings.perplexity_api_key),
        ok=bool(settings.perplexity_api_key),
        detail=_search_detail(db, "perplexity",
                              "No public usage API — balance lives on the API portal."),
        dashboard_url="https://www.perplexity.ai/settings/api")


def serper_panel(db: Session) -> dict:
    """Serper — the SERP engine replacing SerpAPI (News + Jobs, and Iris's web
    search). No public usage API, so we show the engine's own request count + a
    rough spend estimate; the real balance lives on the Serper dashboard."""
    return _panel(
        provider="serper", label="Serper",
        role="SERP engine (News + Jobs) — replacing SerpAPI · free tier 2,500/month",
        configured=bool(settings.serper_api_key),
        ok=bool(settings.serper_api_key),
        detail=_search_detail(db, "serper",
                              "Configured — free tier is 2,500 searches/month; "
                              "balance lives on the Serper dashboard."),
        dashboard_url="https://serper.dev/dashboard")


def anthropic_panel(db: Session) -> dict:
    """LOCAL tally from activity_log (each agent call logs its token usage)."""
    base = dict(provider="anthropic", label="Anthropic (Claude)",
                role="The 9 dashboard agents — Alex + 8 specialists (Opus 4.8) — plus the engine (Sonnet 5 / Opus 4.8)",
                dashboard_url="https://console.anthropic.com/settings/usage")
    if not settings.anthropic_api_key or settings.anthropic_api_key == "not-set":
        return _panel(**base, configured=False, ok=False)
    try:
        rows = (db.query(ActivityLog.agent_id, ActivityLog.activity_metadata)
                .filter(ActivityLog.activity_metadata.isnot(None)).all())
        tokens_in = tokens_out = calls = 0
        cost = 0.0
        per_agent: dict[str, dict] = {}
        for agent_id, meta in rows:
            try:
                data = json.loads(meta)
            except (TypeError, json.JSONDecodeError):
                continue
            if "input_tokens" in data or "output_tokens" in data:
                t_in = int(data.get("input_tokens", 0) or 0)
                t_out = int(data.get("output_tokens", 0) or 0)
                p_in, p_out = _price(data.get("model"))
                row_cost = t_in / 1e6 * p_in + t_out / 1e6 * p_out
                calls += 1
                tokens_in += t_in
                tokens_out += t_out
                cost += row_cost
                slot = per_agent.setdefault(
                    agent_id or "?", {"agent": agent_id or "?", "calls": 0,
                                      "tokens_in": 0, "tokens_out": 0, "cost": 0.0})
                slot["calls"] += 1
                slot["tokens_in"] += t_in
                slot["tokens_out"] += t_out
                slot["cost"] += row_cost
        by_agent = sorted(per_agent.values(), key=lambda a: a["cost"], reverse=True)
        for a in by_agent:
            a["cost"] = round(a["cost"], 3)
        total_calls_all = db.query(func.count(ActivityLog.id)).scalar() or 0
        panel = _panel(
            **base,
            plan=f"{calls} API calls logged (agents + engine)",
            used=round(cost, 2), unit="USD est. (list price per model)",
            detail=(f"{tokens_in:,} tokens in · {tokens_out:,} tokens out — "
                    f"LOCAL tally (activity_log, {total_calls_all} rows), priced "
                    f"per model (Opus 4.8 / Sonnet 5). "
                    f"Official billing lives on the Anthropic console."),
        )
        panel["by_agent"] = by_agent
        return panel
    except Exception as exc:
        logger.warning("[usage] anthropic local tally: %s", exc)
        return _panel(**base, ok=False, error=str(exc)[:160])


def apollo_panel() -> dict:
    return _panel(
        provider="apollo", label="Apollo",
        role="Decision-maker contacts (Inès) — target: Kaspr migration",
        configured=bool(settings.apollo_api_key),
        ok=bool(settings.apollo_api_key),
        detail="Key absent from .env." if not settings.apollo_api_key else
               "Configured — usage visible on the Apollo dashboard.",
        dashboard_url="https://app.apollo.io/#/settings/plans/upgrade")


# ─────────────────────────────────────────────────────────────────────────────
# Aggregate
# ─────────────────────────────────────────────────────────────────────────────

def all_panels(db: Session) -> list[dict]:
    """Every provider card; network ones cached 120 s. Order = page order."""
    return [
        anthropic_panel(db),                                # local, no cache needed
        _cached("serpapi", serpapi_panel),
        serper_panel(db),
        _cached("apify", apify_panel),
        _cached("firecrawl", firecrawl_panel),
        exa_panel(db),
        perplexity_panel(db),
        apollo_panel(),
    ]
