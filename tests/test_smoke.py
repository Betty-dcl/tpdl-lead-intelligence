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
         "/runs", "/performance", "/data", "/login", "/how-it-works"]


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
    # geography NEVER excludes — everything is in scope (Betty wants the world too)
    for loc in ("Dubai, UAE", "Barcelona, Spain", "Munich, Germany", "Boston, USA", "Tokyo, Japan"):
        assert assess_icp("Some Pharma", location=loc)["out_of_scope"] is False, loc


def test_revenue_parser_and_failopen():
    from pipeline.enrich import parse_revenue, estimate_revenue
    from pipeline.config import EngineConfig
    assert parse_revenue("€250 million") == "~€250M (estimated)"
    assert parse_revenue("about $1.2 billion in 2024") == "~$1.2B (estimated)"
    assert parse_revenue("CHF 300M") == "~CHF300M (estimated)"
    assert parse_revenue("revenue of 45 million euros") == "~€45M (estimated)"
    assert parse_revenue("unknown") is None
    assert parse_revenue("") is None
    assert parse_revenue(None) is None
    # estimate_revenue is fail-open: dry-run (not live) → None, never raises
    assert estimate_revenue(EngineConfig(live=False), "Whatever Co") is None


def test_hq_location_enrichment():
    from pipeline.enrich import (parse_hq_location, needs_city,
                                 estimate_hq_location)
    from pipeline.config import EngineConfig
    # parser: clean 'City, Country' kept; junk/sentences/unknown rejected
    assert parse_hq_location("Barcelona, Spain") == "Barcelona, Spain"
    assert parse_hq_location("Madrid, Spain.\nFounded 1989") == "Madrid, Spain"
    assert parse_hq_location("Basel") == "Basel"
    assert parse_hq_location("unknown") is None
    assert parse_hq_location("The company does not publicly disclose this") is None
    assert parse_hq_location("") is None
    assert parse_hq_location(None) is None
    # a rambling sentence with no comma and >4 words is rejected
    assert parse_hq_location("It has offices in several European countries today") is None
    # needs_city: enrich when empty / unknown / a bare country; keep real cities
    assert needs_city(None) is True
    assert needs_city("Spain") is True
    assert needs_city("unknown") is True
    assert needs_city("Barcelona, Spain") is False
    assert needs_city("Les Ulis") is False        # a free city string is kept
    # estimate_hq_location is fail-open: dry-run → None, never raises
    assert estimate_hq_location(EngineConfig(live=False), "Whatever Co") is None


def test_serpapi_drains_then_serper_backup():
    """Betty's SERP strategy: use up SerpAPI first, then fall back to Serper
    once SerpAPI is out — both keys live, never crash the run."""
    from pipeline import research as R
    from pipeline.research import (RawDoc, SerpApiExhausted, _check_serpapi_quota,
                                   serpapi_exhausted)
    from pipeline.config import EngineConfig

    # quota body raises; a normal body passes through untouched
    import pytest
    with pytest.raises(SerpApiExhausted):
        _check_serpapi_quota({"error": "Your account has run out of searches."})
    assert _check_serpapi_quota({"news_results": [1]}) == {"news_results": [1]}

    cfg = EngineConfig(live=True)
    cfg.serpapi_key, cfg.serper_api_key = "sa", "sr"
    calls = {"serpapi": 0, "serper": 0}

    def fake_serpapi_news(c, company, gl=None, hl=None):
        calls["serpapi"] += 1
        raise SerpApiExhausted("run out of searches")

    def fake_serper_news(c, company, gl=None, hl=None):
        calls["serper"] += 1
        return [RawDoc(source="serper_news", url="u", title="t", text="x")]

    orig = (R.serpapi_news, R.serper_news)
    R.serpapi_news, R.serper_news = fake_serpapi_news, fake_serper_news
    try:
        out = R.serp_news(cfg, "Acme")
        assert len(out) == 1 and out[0].source == "serper_news"
        assert serpapi_exhausted(cfg) is True           # flag set for the run
        R.serp_news(cfg, "Beta")                         # 2nd company
        assert calls["serpapi"] == 1                     # SerpAPI not called again
        assert calls["serper"] == 2                      # Serper served both
    finally:
        R.serpapi_news, R.serper_news = orig


def test_market_tier():
    from app.tools.icp import market_tier
    # core market = CH / ES / Middle East / rest of Europe
    assert market_tier("Basel, Switzerland") == "core"
    assert market_tier("Barcelona, Spain") == "core"
    assert market_tier("Dubai, UAE") == "core"
    assert market_tier("Munich, Germany") == "core"
    # world = still in scope, just lower priority
    assert market_tier("Boston, USA") == "world"
    assert market_tier("Tokyo, Japan") == "world"


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


def _csv_header(text: str) -> str:
    """Header line, skipping the Excel `sep=;` sentinel and the UTF-8 BOM."""
    lines = text.lstrip("﻿").splitlines()
    return lines[1] if lines and lines[0].startswith("sep=") else lines[0]


def test_intel_export_csv(client):
    r = client.get("/api/intel/export.csv?scope=run")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    # Excel-friendly: UTF-8 BOM + `sep=;` sentinel + semicolon delimiter so the
    # file opens as clean columns with correct accents in any Excel locale.
    assert r.text.startswith("﻿sep=;")
    header = _csv_header(r.text)
    assert ";" in header
    # Identity + status + score + full context (summary, signals, tech stack).
    for col in ("Company Name", "Sector", "Website", "Revenue", "Status",
                "Assessed Score", "Intelligence Summary",
                "Signal 1 Corroboration (0-2)", "Tech Stack Summary"):
        assert col in header
    # ONE sector column only (no redundant "Sector Bucket").
    assert "Sector Bucket" not in header
    # Market Tier removed.
    assert "Market Tier" not in header


def test_intel_export_all_scope_has_evolution(client):
    """scope=all spans several runs, so the evolution columns must appear;
    an all-new single run prunes them (they'd be empty)."""
    header = _csv_header(client.get("/api/intel/export.csv?scope=all").text)
    for col in ("Delta vs May", "Score Trajectory", "Status"):
        assert col in header


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


def test_company_brief_pdf(client):
    """Per-company PDF brief: a real PDF for an existing company, 404 otherwise."""
    from app.models import Company
    from app.database import SessionLocal
    with SessionLocal() as db:
        name = db.query(Company.name).first()[0]
    r = client.get(f"/api/intel/companies/{name}/brief.pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:5] == b"%PDF-"
    assert "attachment" in r.headers.get("content-disposition", "")
    assert client.get("/api/intel/companies/NoSuchCompanyXYZ/brief.pdf").status_code == 404


def test_view_pdf_snapshot(client):
    """POST /view.pdf renders a branded PDF from whatever columns/rows the client
    posts (WYSIWYG snapshot of a filtered view)."""
    payload = {
        "title": "Companies that keep coming back",
        "subtitle": "Recurring · sort: Biggest riser · 2 shown",
        "columns": ["Company", "Location", "Seen", "May 25", "Jul 17", "Since first"],
        "rows": [["LETI Pharma", "Madrid, Spain", "×2", "0.0", "6.2", "+6.2"],
                 ["Medinova", "Zurich, Switzerland", "×2", "0.0", "6.0", "+6.0"]],
        "widths": [30, 28, 10, 11, 11, 13],
        "filename": "tpdl_recurring.pdf",
    }
    r = client.post("/api/intel/view.pdf", json=payload)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:5] == b"%PDF-"
    assert "tpdl_recurring.pdf" in r.headers.get("content-disposition", "")


def test_export_rich_csv_filtered_by_names(client):
    """POST names → full-depth CSV for exactly those, in the posted order, with the
    same rich columns as the run export (summary, signal sources, trajectory)."""
    from app.models import Company
    from app.database import SessionLocal
    with SessionLocal() as db:
        names = [n for (n,) in db.query(Company.name).limit(3).all()]
    r = client.post("/api/intel/export_rich.csv",
                    json={"names": names, "filename": "tpdl_recurring.csv"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert r.text.startswith("﻿sep=;")
    header = r.text.lstrip("﻿").splitlines()[1]
    for col in ("Company Name", "Intelligence Summary", "Signal 1 URLs",
                "Signal 1 Corroboration (0-2)", "Tech Stack Summary"):
        assert col in header
    # rows are exactly the posted names, in order
    body = r.text.lstrip("﻿").splitlines()[2:]
    got = [ln.split(";")[0].strip('"') for ln in body if ln.strip()]
    assert got == names


def test_view_briefs_pdf(client):
    """POST names → a detailed multi-company brief PDF (one full brief per name)."""
    from app.models import Company
    from app.database import SessionLocal
    with SessionLocal() as db:
        names = [n for (n,) in db.query(Company.name).limit(2).all()]
    r = client.post("/api/intel/view_briefs.pdf",
                    json={"names": names, "filename": "tpdl_recurring_briefs.pdf",
                          "title": "Recurring"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:5] == b"%PDF-"
    # empty view still yields a valid (1-page) PDF, never a crash
    empty = client.post("/api/intel/view_briefs.pdf", json={"names": []})
    assert empty.status_code == 200 and empty.content[:5] == b"%PDF-"


def test_compare_runs_span_full_folds_in_middle(client):
    """span=full folds every run between from/to into the comparison, so a company
    scored at the start AND a middle run counts as recurring (not '0 in both')."""
    runs = client.get("/api/intel/runs").json()["runs"]
    if len(runs) < 3:
        import pytest
        pytest.skip("need ≥3 runs to exercise the middle")
    lo, hi = runs[0]["run_id"], runs[-1]["run_id"]
    two = client.get(f"/api/intel/compare?from_run={lo}&to_run={hi}&span=two").json()
    full = client.get(f"/api/intel/compare?from_run={lo}&to_run={hi}&span=full").json()
    # full spans all the run dates in [lo, hi]; two spans none
    assert len(full["span_runs"]) >= 3
    assert two["span_runs"] == []
    # folding in the middle recovers recurring companies the endpoint-only view misses
    two_common = two["summary"]["rising"] + two["summary"]["fading"] + two["summary"]["stable"]
    full_common = full["summary"]["rising"] + full["summary"]["fading"] + full["summary"]["stable"]
    assert full_common > two_common
    # full-span movers carry a trajectory across the middle runs
    movers = [c for c in full["companies"] if c["delta"] is not None]
    assert movers and any(len(c["trajectory"]) >= 2 for c in movers)
