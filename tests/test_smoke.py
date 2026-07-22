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

PAGES = ["/", "/intel", "/intel/company?c=Roche", "/marketing", "/contacts",
         "/today", "/runs", "/performance", "/data", "/login"]


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
    body = r.json()
    assert body["name"] == a_company
    # Neotek-movement fields are always present (may be null if never in Neotek)
    assert {"neotek_score", "delta", "reappeared"} <= set(body)
    # Per-signal score derivation is exposed
    for sig in body["signals"]:
        assert {"points", "max", "note"} <= set(sig["corroboration"])


def test_intel_run_summary(client):
    data = client.get("/api/intel/run").json()
    assert data["has_run"] is True
    assert {"run_date", "companies", "eligible", "bands", "neotek"} <= set(data)
    b = data["bands"]
    assert b["act_now"] + b["monitor"] + b["weak"] + b["none"] == data["companies"]
    # Movement vs Neotek: risers + faders + stable never exceeds reappeared
    n = data["neotek"]
    assert n["risers"] + n["faders"] + n["stable"] <= n["reappeared"]


def test_intel_trajectory(client, a_company):
    data = client.get(f"/api/intel/companies/{a_company}/trajectory").json()
    assert data["company"] == a_company
    # At least the current run point exists; last point is the current one
    assert len(data["points"]) >= 1
    assert data["points"][-1]["current"] is True


def test_intel_company_has_geo_region(client, a_company):
    body = client.get(f"/api/intel/companies/{a_company}").json()
    assert body["geo_region"] in {"CH", "ES", "USA", "Middle East",
                                  "Europe", "APAC", "Other"}


def test_geo_region_bucketing():
    from app.tools.radars import geo_region
    assert geo_region("Basel, Switzerland") == "CH"
    assert geo_region("Barcelona, Spain") == "ES"
    assert geo_region("Dubai, UAE") == "Middle East"
    assert geo_region("San Diego, California, USA") == "USA"
    assert geo_region("Tokyo, Japan") == "APAC"
    assert geo_region("Munich, Germany") == "Europe"
    assert geo_region("Toronto, Ontario, Canada") == "Other"
    assert geo_region(None) == "Other"


def test_icp_targeting_classifier():
    from app.tools.icp import assess_icp, revenue_below_floor
    # confirmed campaign targets are never excluded
    assert assess_icp("Cantabria Labs", "Dermatology", "Dermatology", "~€200M")["out_of_scope"] is False
    assert assess_icp("Leti Pharma", "Pharma", "Pharma", "€200M–300M")["out_of_scope"] is False
    # hard exclusions
    assert assess_icp("Zuhlke", "Unknown", "Unknown", "CHF 300M+")["out_of_scope"] is True
    assert assess_icp("Lonza", "Unknown", "Unknown", "~$6B+")["out_of_scope"] is True
    assert assess_icp("Tiny Diagnostics", "Diagnostics", "Diagnostics", "~€45M")["out_of_scope"] is True
    # private / undisclosed revenue is KEPT; billions kept; regional partials kept
    assert assess_icp("Ferrer", "Pharma", "Pharma", "NA")["out_of_scope"] is False
    assert revenue_below_floor("~$6B+") is False
    assert revenue_below_floor("~$77.3M (regional listing)") is False
    assert revenue_below_floor("private") is False
    assert revenue_below_floor("~€45M") is True
    # curated non-brand-owners (Nathalie's rule) are excluded by name
    assert assess_icp("Evotec SE")["out_of_scope"] is True          # CDMO/CRO
    assert assess_icp("DocMorris")["out_of_scope"] is True          # pharmacy/distribution
    assert assess_icp("PharmaRelations")["out_of_scope"] is True    # consulting
    # brand-owner targets in the discovery batch are KEPT
    assert assess_icp("Recordati S.p.A.")["out_of_scope"] is False
    assert assess_icp("Laboratoires Pierre Fabre")["out_of_scope"] is False
    # no short-substring false positives ("ey"/"cgi" must not match journey/Berkeley words)
    assert assess_icp("Journey Medical")["out_of_scope"] is False
    # geo: CH/ES/Middle East/Europe are phase-1/2 (in); USA/APAC are phase 3 (out)
    assert assess_icp("Some Pharma", location="Dubai, UAE")["out_of_scope"] is False   # ME in
    assert assess_icp("Some Pharma", location="Barcelona, Spain")["out_of_scope"] is False
    assert assess_icp("Some Pharma", location="Munich, Germany")["out_of_scope"] is False
    assert assess_icp("Some Pharma", location="Boston, USA")["out_of_scope"] is True    # phase 3
    assert assess_icp("Some Pharma", location="Tokyo, Japan")["out_of_scope"] is True   # phase 3


def test_market_country_detection():
    from app.tools.radars import detect_market_country, detect_country
    assert detect_market_country("Munich, Germany") == "DE"
    assert detect_market_country("Milan, Italy") == "IT"
    assert detect_market_country("Dubai, UAE") == "AE"
    assert detect_market_country("Copenhagen, Denmark") == "DK"
    assert detect_market_country("Nowhere") is None
    # detect_country stays CH/ES-only (Inès radars unchanged)
    assert detect_country("Munich, Germany") is None
    assert detect_country("Basel, Switzerland") == "CH"


def test_intel_runs_list(client):
    data = client.get("/api/intel/runs").json()
    assert data["count"] >= 1
    for r in data["runs"]:
        assert {"run_id", "run_date", "label", "companies", "is_neotek"} <= set(r)
    # oldest → newest
    dates = [r["run_date"] for r in data["runs"] if r["run_date"]]
    assert dates == sorted(dates)


def test_intel_compare_two_runs(client):
    runs = client.get("/api/intel/runs").json()["runs"]
    if len(runs) < 2:
        pytest.skip("need at least two runs to compare")
    frm, to = runs[0]["run_id"], runs[-1]["run_id"]
    d = client.get(f"/api/intel/compare?from_run={frm}&to_run={to}").json()
    s = d["summary"]
    assert {"new", "dropped", "rising", "fading", "stable", "common"} <= set(s)
    # every company carries a status; delta is null exactly for new/dropped
    for c in d["companies"]:
        assert c["status"] in {"new", "dropped", "rising", "fading", "stable"}
        assert (c["delta"] is None) == (c["status"] in {"new", "dropped"})
    # a company only in the later run is "new"; only in baseline is "dropped"
    assert s["rising"] + s["fading"] + s["stable"] == s["common"]


def test_intel_compare_unknown_runs_404(client):
    r = client.get("/api/intel/compare?from_run=nope&to_run=nada")
    assert r.status_code == 404


def test_intel_export_csv(client):
    r = client.get("/api/intel/export.csv?scope=run")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    header = r.text.splitlines()[0]
    assert "Delta vs Neotek" in header and "Assessed Score" in header


def test_contacts_radars(client):
    data = client.get("/api/contacts/radars").json()
    assert {"switzerland", "spain", "counts", "latest_run"} <= set(data)
    for entry in data["switzerland"] + data["spain"]:
        assert {"delta", "reappeared", "fresh", "run_date"} <= set(entry)


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
