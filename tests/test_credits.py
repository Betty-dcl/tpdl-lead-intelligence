"""Usage & credits page — offline tests (provider endpoints are mocked)."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.tools import usage


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _clear_cache():
    usage._CACHE.clear()
    yield
    usage._CACHE.clear()


def test_serpapi_panel_parses_account(monkeypatch):
    monkeypatch.setattr(usage.settings, "serpapi_key", "test-key")
    monkeypatch.setattr(usage, "_get_json", lambda url, headers=None: {
        "plan_name": "Developer", "searches_per_month": 5000,
        "this_month_usage": 1200, "plan_searches_left": 3800,
        "account_email": "betty@thepharmadatalab.com",
    })
    p = usage.serpapi_panel()
    assert p["ok"] and p["configured"]
    assert (p["plan"], p["used"], p["limit"], p["remaining"]) == ("Developer", 1200, 5000, 3800)


def test_firecrawl_panel_parses_credits(monkeypatch):
    monkeypatch.setattr(usage.settings, "firecrawl_api_key", "fc-test")
    monkeypatch.setattr(usage, "_get_json", lambda url, headers=None: {
        "data": {"remainingCredits": 4400, "planCredits": 5000}})
    p = usage.firecrawl_panel()
    assert p["remaining"] == 4400 and p["limit"] == 5000 and p["used"] == 600


def test_panel_degrades_to_error_not_crash(monkeypatch):
    monkeypatch.setattr(usage.settings, "apify_token", "t")

    def boom(url, headers=None):
        raise RuntimeError("provider down")
    monkeypatch.setattr(usage, "_get_json", boom)
    p = usage.apify_panel()
    assert p["configured"] and not p["ok"] and "provider down" in p["error"]


def test_unconfigured_provider_is_flagged(monkeypatch):
    monkeypatch.setattr(usage.settings, "serpapi_key", "")
    p = usage.serpapi_panel()
    assert not p["configured"] and not p["ok"]


def test_anthropic_local_tally(monkeypatch, client):
    """Sums input/output tokens from activity_log rows (shape from base.py)."""
    from app.database import SessionLocal
    from app.models import ActivityLog
    with SessionLocal() as db:
        marker = "usage-test-marker"
        db.add(ActivityLog(agent_id="hugo", action=marker,
                           activity_metadata=json.dumps(
                               {"input_tokens": 1000, "output_tokens": 500,
                                "model": "claude-opus-4-8"})))
        db.commit()
        try:
            p = usage.anthropic_panel(db)
            assert p["configured"] and p["ok"]
            assert p["used"] is not None and p["used"] > 0   # est. cost in USD
            assert "tokens in" in p["detail"]
        finally:
            db.query(ActivityLog).filter(ActivityLog.action == marker).delete()
            db.commit()


def test_api_credits_endpoint_shape(monkeypatch, client):
    fake = [usage._panel("serpapi", "SerpAPI", used=1, limit=10, remaining=9)]
    monkeypatch.setattr(usage, "all_panels", lambda db: fake)
    res = client.get("/api/credits")
    assert res.status_code == 200
    body = res.json()
    assert body["panels"][0]["provider"] == "serpapi"
    assert body["summary"]["configured"] == 1
    assert body["summary"]["errors"] == 0


def test_credits_page_renders(client):
    res = client.get("/credits")
    assert res.status_code == 200
    assert "Usage &amp; credits" in res.text or "Usage & credits" in res.text
    assert "creditsPage" in res.text


def test_anthropic_by_agent_breakdown(monkeypatch, client):
    from app.database import SessionLocal
    from app.models import ActivityLog
    with SessionLocal() as db:
        marker = "usage-agent-breakdown-marker"
        db.add(ActivityLog(agent_id="maya", action=marker,
                           activity_metadata=json.dumps(
                               {"input_tokens": 2000, "output_tokens": 100})))
        db.commit()
        try:
            p = usage.anthropic_panel(db)
            agents = {a["agent"] for a in p.get("by_agent", [])}
            assert "maya" in agents
            maya = next(a for a in p["by_agent"] if a["agent"] == "maya")
            assert maya["calls"] >= 1 and maya["cost"] > 0
        finally:
            db.query(ActivityLog).filter(ActivityLog.action == marker).delete()
            db.commit()


def test_engine_runs_endpoint(client):
    res = client.get("/api/credits/runs")
    assert res.status_code == 200
    runs = res.json()["runs"]
    assert isinstance(runs, list)
    if runs:  # DB seeded with the 25/05 reference run
        r = runs[0]
        assert {"run_id", "companies", "eligible", "run_date", "imported_at"} <= set(r)
        assert r["companies"] > 0


def test_loader_top_and_names():
    from pipeline import loader
    top = loader.load_top(3)
    if not top:
        pytest.skip("companies table empty")
    assert len(top) == 3
    # sorted by score desc, identity carried over
    assert "historical_context" in top[0].identity
    named = loader.load_names([top[0].name, "Company That Does Not Exist XYZ"])
    assert named[0].sector == top[0].sector
    assert named[1].identity == {}  # unknown → runnable, no identity


def test_loader_lunch_is_ch_es_only():
    from pipeline import loader
    from app.tools.radars import detect_country
    pool = loader.load_lunch()
    if not pool:
        pytest.skip("companies table empty")
    assert all(detect_country(c.identity["location"]) in ("CH", "ES") for c in pool)


def test_estimator_math_and_quota_verdict(monkeypatch):
    from pipeline import estimate as est_mod
    est = est_mod.estimate_run(20)
    assert est.serp_searches == 60 and est.exa_requests == 60   # 3 SERP/company (News+Jobs+registry)
    # 20 × (extract 0.022 + score 0.0325) ≈ 1.09
    assert 0.9 < est.model_cost_usd < 1.3
    assert est.model_cost_batch_usd == round(est.model_cost_usd * 0.5, 2)
    # quota verdict: enough vs not enough (usage.serpapi_panel mocked)
    monkeypatch.setattr("app.tools.usage.serpapi_panel", lambda: usage._panel(
        "serpapi", "SerpAPI", remaining=250, plan="Free Plan"))
    assert "OK" in est_mod.serp_quota_check(est)
    monkeypatch.setattr("app.tools.usage.serpapi_panel", lambda: usage._panel(
        "serpapi", "SerpAPI", remaining=10, plan="Free Plan"))
    assert "INSUFFICIENT" in est_mod.serp_quota_check(est)


def test_ttl_cache_avoids_double_fetch(monkeypatch):
    calls = {"n": 0}

    def counting():
        calls["n"] += 1
        return {"x": calls["n"]}
    assert usage._cached("k", counting) == {"x": 1}
    assert usage._cached("k", counting) == {"x": 1}   # served from cache
    assert calls["n"] == 1
