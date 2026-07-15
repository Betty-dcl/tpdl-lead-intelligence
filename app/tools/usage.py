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

# Opus 4.8 list price (USD per MTok) — for the local cost estimate only.
_OPUS_IN_PER_MTOK = 5.0
_OPUS_OUT_PER_MTOK = 25.0

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


def exa_panel() -> dict:
    return _panel(
        provider="exa", label="Exa",
        role="Neural search ×3 (news / leadership / M&A) — engine Step 2",
        configured=bool(settings.exa_api_key),
        ok=bool(settings.exa_api_key),
        detail="No public usage API — balance lives on the Exa dashboard.",
        dashboard_url="https://dashboard.exa.ai")


def perplexity_panel() -> dict:
    return _panel(
        provider="perplexity", label="Perplexity",
        role="Sonar, financial press PE/M&A — corroborates, never anchors",
        configured=bool(settings.perplexity_api_key),
        ok=bool(settings.perplexity_api_key),
        detail="No public usage API — balance lives on the API portal.",
        dashboard_url="https://www.perplexity.ai/settings/api")


def anthropic_panel(db: Session) -> dict:
    """LOCAL tally from activity_log (each agent call logs its token usage)."""
    base = dict(provider="anthropic", label="Anthropic (Claude)",
                role="The 8 dashboard agents (Opus 4.8) + the engine (Sonnet 5 / Opus 4.8)",
                dashboard_url="https://console.anthropic.com/settings/usage")
    if not settings.anthropic_api_key or settings.anthropic_api_key == "not-set":
        return _panel(**base, configured=False, ok=False)
    try:
        rows = (db.query(ActivityLog.agent_id, ActivityLog.activity_metadata)
                .filter(ActivityLog.activity_metadata.isnot(None)).all())
        tokens_in = tokens_out = calls = 0
        per_agent: dict[str, dict] = {}
        for agent_id, meta in rows:
            try:
                data = json.loads(meta)
            except (TypeError, json.JSONDecodeError):
                continue
            if "input_tokens" in data or "output_tokens" in data:
                t_in = int(data.get("input_tokens", 0) or 0)
                t_out = int(data.get("output_tokens", 0) or 0)
                calls += 1
                tokens_in += t_in
                tokens_out += t_out
                slot = per_agent.setdefault(
                    agent_id or "?", {"agent": agent_id or "?", "calls": 0,
                                      "tokens_in": 0, "tokens_out": 0})
                slot["calls"] += 1
                slot["tokens_in"] += t_in
                slot["tokens_out"] += t_out
        cost = tokens_in / 1e6 * _OPUS_IN_PER_MTOK + tokens_out / 1e6 * _OPUS_OUT_PER_MTOK
        by_agent = sorted(per_agent.values(), key=lambda a: (
            a["tokens_in"] * _OPUS_IN_PER_MTOK + a["tokens_out"] * _OPUS_OUT_PER_MTOK),
            reverse=True)
        for a in by_agent:
            a["cost"] = round(a["tokens_in"] / 1e6 * _OPUS_IN_PER_MTOK
                              + a["tokens_out"] / 1e6 * _OPUS_OUT_PER_MTOK, 3)
        total_calls_all = db.query(func.count(ActivityLog.id)).scalar() or 0
        panel = _panel(
            **base,
            plan=f"{calls} agent calls logged",
            used=round(cost, 2), unit="USD est. (Opus 4.8 list price)",
            detail=(f"{tokens_in:,} tokens in · {tokens_out:,} tokens out — "
                    f"LOCAL tally (activity_log, {total_calls_all} rows). "
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
        _cached("apify", apify_panel),
        _cached("firecrawl", firecrawl_panel),
        exa_panel(),
        perplexity_panel(),
        apollo_panel(),
    ]
