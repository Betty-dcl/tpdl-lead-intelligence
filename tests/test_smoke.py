"""Smoke tests — fast checks that the platform is wired correctly.

No Anthropic API calls are made: chat/brief generation is only tested at the
command-dispatch level (the augmented prompt is built from the DB, Claude is
never called). Run with:  .venv/bin/python -m pytest tests/ -q
"""
import pytest
from fastapi.testclient import TestClient

from app.config import AgentID
from app.database import SessionLocal
from app.main import app
from app.models import Company

EXPECTED_ROSTER = {a.value for a in AgentID}  # manager + 7 specialists

PAGES = ["/", "/intel", "/marketing", "/contacts", "/today",
         "/performance", "/data", "/login"]


@pytest.fixture(scope="module")
def client():
    # Context manager runs the lifespan (init_db + signals sync), like uvicorn.
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def a_company():
    with SessionLocal() as db:
        c = db.query(Company).first()
    if c is None:
        pytest.skip("companies table is empty — run import_csv.py first")
    return c.name


# ── Pages ─────────────────────────────────────────────────────────────────────

def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "healthy"}


@pytest.mark.parametrize("path", PAGES)
def test_page_renders(client, path):
    r = client.get(path)
    assert r.status_code == 200, f"{path} returned {r.status_code}"
    assert "<html" in r.text.lower() or "<!doctype" in r.text.lower()


def test_unknown_page_is_404(client):
    assert client.get("/nonexistent").status_code == 404
    r = client.get("/api/nonexistent")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/json")


# ── Agents ────────────────────────────────────────────────────────────────────

def test_agent_roster(client):
    r = client.get("/api/agents")
    assert r.status_code == 200
    ids = {a["id"] for a in r.json()}
    assert ids == EXPECTED_ROSTER, f"roster mismatch: {ids ^ EXPECTED_ROSTER}"


@pytest.mark.parametrize("agent_id", sorted(EXPECTED_ROSTER))
def test_agent_profile_page(client, agent_id):
    assert client.get(f"/agent/{agent_id}").status_code == 200


def test_unknown_agent_404(client):
    assert client.get("/api/agents/ghost").status_code == 404
    assert client.get("/agent/ghost").status_code == 404


# ── /generate dispatch (workspace "Generate brief" button) ───────────────────
# Dispatch-level only: builds the augmented prompt from the DB, no Claude call.

SALES_AGENTS = ["hugo", "maya", "ines", "julie"]


@pytest.mark.parametrize("agent_id", SALES_AGENTS)
def test_generate_dispatch(client, a_company, agent_id):
    from app.agents import get_agent_class
    with SessionLocal() as db:
        agent = get_agent_class(agent_id).load(db, agent_id)
        meta = agent._dispatch_command(f"/generate {a_company}")
    assert meta is not None, f"{agent_id} does not dispatch /generate"
    assert meta.get("augmented_message")
    assert a_company in meta["augmented_message"]


@pytest.mark.parametrize("agent_id", SALES_AGENTS)
def test_generate_dispatch_edge_cases(client, agent_id):
    from app.agents import get_agent_class
    with SessionLocal() as db:
        agent = get_agent_class(agent_id).load(db, agent_id)
        no_name = agent._dispatch_command("/generate")
        not_found = agent._dispatch_command("/generate Zzz-Unknown-Corp-999")
    assert no_name is not None and no_name.get("augmented_message")
    assert not_found is not None and not_found.get("augmented_message")


# ── Data APIs ─────────────────────────────────────────────────────────────────

def test_intel_stats_shape(client):
    data = client.get("/api/intel/stats").json()
    assert {"pipeline", "score_distribution", "signal_coverage",
            "sector_distribution"} <= set(data)
    assert data["pipeline"]["total_companies"] >= 0


def test_intel_company_detail(client, a_company):
    r = client.get(f"/api/intel/companies/{a_company}")
    assert r.status_code == 200
    assert r.json()["name"] == a_company


def test_contacts_radars(client):
    data = client.get("/api/contacts/radars").json()
    assert {"switzerland", "spain", "counts"} <= set(data)


def test_newsletter_editions_seeded(client):
    rows = client.get("/api/marketing/newsletter/editions").json()
    assert len(rows) >= 9   # first call seeds the 9-edition plan


def test_performance_summary(client):
    data = client.get("/api/performance/summary").json()
    assert "total_tasks" in data and "recent_7d" in data


# ── Guard rails ───────────────────────────────────────────────────────────────

def test_onedrive_refresh_rejects_arbitrary_url(client):
    r = client.post("/api/onedrive/refresh", json={"url": "https://evil.example/x.csv"})
    assert r.status_code == 422   # SSRF guard: only OneDrive/SharePoint hosts

    r = client.post("/api/onedrive/refresh", json={"url": "http://1drv.ms/x"})
    assert r.status_code == 422   # https only


def test_carousel_generate_validates_formats(client):
    r = client.post("/api/marketing/carousel/generate-async",
                    json={"subject": "test", "formats": ["bogus"]})
    assert r.status_code == 422

    r = client.post("/api/marketing/carousel/generate-async",
                    json={"subject": "  ", "formats": ["linkedin"]})
    assert r.status_code == 422


def test_pdf_export_handles_unicode(client):
    """Unicode in subject (→ HTTP header filename) and content (→ Helvetica) must
    not 500 the export — both used to crash separately."""
    r = client.post("/api/marketing/carousel/export-pdf", json={
        "subject": "Stack consolidation → 2026",
        "content": "TITLE: X\nSECTION 1 — Why\n- 50% ↑, ≥ €10M, café – done."})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:5] == b"%PDF-"


def test_pptx_export_handles_unicode(client):
    r = client.post("/api/marketing/deck/export-pptx", json={
        "subject": "Q3 medtech → review",
        "content": "TITLE: Q3\nSLIDE 1: Momentum / M&A ↑ 20%"})
    assert r.status_code == 200
    assert r.content[:2] == b"PK"          # valid .pptx (zip) container


def test_export_rejects_empty_content(client):
    for path in ("/api/marketing/carousel/export-pdf", "/api/marketing/deck/export-pptx"):
        r = client.post(path, json={"subject": "x", "content": "   "})
        assert r.status_code == 422
