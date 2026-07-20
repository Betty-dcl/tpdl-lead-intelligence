"""Agent-wiring tests for the new free fixes — signal→role, Julie↔contacts,
Maya /recurring on run history. DB rows are inserted then cleaned up; no API."""
from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    with TestClient(app) as c:      # startup runs init_db → creates run_snapshots
        yield c


# ── #18 signal → role targeting (in code, not just the prompt) ──────────────

def test_titles_for_signal():
    from app.tools import apollo
    assert "Chief Digital Officer" in apollo.titles_for_signal("digital_initiative")
    assert apollo.titles_for_signal("pe_event") == ("CEO", "CFO")
    assert apollo.titles_for_signal(None) == apollo.DEFAULT_TITLES
    assert apollo.titles_for_signal("unknown_signal") == apollo.DEFAULT_TITLES


def test_ines_contacts_uses_signal_driven_titles(client):
    """Inès's /contacts augments with roles derived from the lead signal."""
    from app.agents import AGENT_CLASSES
    from app.database import SessionLocal
    from app.models import Company
    with SessionLocal() as db:
        c = (db.query(Company).filter(Company.s1_category.isnot(None)).first())
        if c is None:
            pytest.skip("no company with a signal in DB")
        name, lead = c.name, c.s1_category
        ines = AGENT_CLASSES["ines"].load(db, "ines")
        meta = ines._dispatch_command(f"/contacts {name}")
    from app.tools import apollo
    expected = apollo.titles_for_signal(lead)
    assert any(t in meta["augmented_message"] for t in expected)


# ── #20 Apollo real fetch (gated; parsing verified offline) ─────────────────

def test_apollo_not_configured(monkeypatch):
    from app.tools import apollo
    monkeypatch.setattr(apollo.settings, "apollo_api_key", "")
    with pytest.raises(apollo.ApolloNotConfigured):
        apollo.fetch_contacts("Acme")


def test_apollo_fetch_parses_people(monkeypatch):
    import json
    import urllib.request
    from app.tools import apollo
    monkeypatch.setattr(apollo.settings, "apollo_api_key", "test-key")

    class FakeResp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self):
            return json.dumps({"people": [
                {"name": "Jane Roe", "title": "Chief Digital Officer",
                 "email": "jane@acme.com", "linkedin_url": "https://linkedin.com/in/jane",
                 "city": "Zurich", "country": "Switzerland"},
                {"first_name": "Marc", "last_name": "Dubois", "title": "CFO"},
            ]}).encode()

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=30: FakeResp())
    out = apollo.fetch_contacts("Acme", ("Chief Digital Officer", "CFO"))
    assert [p["full_name"] for p in out] == ["Jane Roe", "Marc Dubois"]
    assert out[0]["location"] == "Zurich, Switzerland"
    assert out[1]["email"] is None                       # missing fields → None, no crash


def test_apollo_fetch_degrades_on_http_error(monkeypatch):
    import urllib.error
    import urllib.request
    from app.tools import apollo
    monkeypatch.setattr(apollo.settings, "apollo_api_key", "test-key")

    def boom(req, timeout=30):
        raise urllib.error.HTTPError("url", 429, "Too Many Requests", {}, None)
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    assert apollo.fetch_contacts("Acme") == []           # never crashes the caller


# ── #17 Julie writes TO Inès's stored contact ──────────────────────────────

def test_julie_draft_addresses_stored_contact(client):
    from app.agents import AGENT_CLASSES
    from app.database import SessionLocal
    from app.models import Company, Contact
    with SessionLocal() as db:
        c = db.query(Company).filter(Company.icp_flag.is_(False)).first()
        if c is None:
            pytest.skip("no company in DB")
        marker = Contact(
            company_name=c.name, full_name="Zzy Testcontact",
            title="Chief Digital Officer", function="digital", seniority="c_level",
            language="es", crm_segment=2, premium=False,
        )
        db.add(marker)
        db.commit()
        try:
            julie = AGENT_CLASSES["julie"].load(db, "julie")
            meta = julie._dispatch_command(f"/draft {c.name}")
            msg = meta["augmented_message"]
            assert "Zzy Testcontact" in msg                 # writes TO the person
            assert "SPANISH" in msg                          # language honoured
            assert "cold pitch" in msg.lower() or "DEAD" in msg  # warm philosophy
            assert meta["metadata"]["recipient"] == "Zzy Testcontact"
        finally:
            db.query(Contact).filter(Contact.full_name == "Zzy Testcontact").delete()
            db.commit()


# ── Hugo /rerun — explains the engine trigger, never fabricates a refresh ───

def test_hugo_rerun_explains_without_fabricating(client):
    from app.agents import AGENT_CLASSES
    from app.database import SessionLocal
    with SessionLocal() as db:
        hugo = AGENT_CLASSES["hugo"].load(db, "hugo")
        meta = hugo._dispatch_command("/rerun")
        assert meta["action"] == "rerun_explained"
        msg = meta["augmented_message"].lower()
        assert "dry-run" in msg and "live" in msg
        assert "never" in msg           # instructed not to claim a refresh happened
        assert isinstance(meta["metadata"]["live_ready"], bool)


# ── Iris dispatch (was entirely untested) ──────────────────────────────────

def test_iris_research_needs_topic(client):
    from app.agents import AGENT_CLASSES
    from app.database import SessionLocal
    with SessionLocal() as db:
        iris = AGENT_CLASSES["iris"].load(db, "iris")
        meta = iris._dispatch_command("/research")
        assert meta["action"] == "researched" and "no topic" in meta["task_title"]


def test_iris_research_and_themes(client, monkeypatch):
    from app.agents import AGENT_CLASSES, iris as iris_mod
    from app.database import SessionLocal
    # Stub the live web search so the dispatch test never touches the network.
    monkeypatch.setattr(iris_mod, "_research", lambda q: "- Some finding (source: x)")
    with SessionLocal() as db:
        iris = AGENT_CLASSES["iris"].load(db, "iris")
        r = iris._dispatch_command("/research CRM in pharma")
        assert r["metadata"]["topic"] == "CRM in pharma"
        t = iris._dispatch_command("/themes dental")
        assert t["action"] == "scored_themes" and t["metadata"]["sector"] == "dental"


# ── Marc dispatch (was entirely untested) ───────────────────────────────────

def test_marc_angles_and_content(client):
    from app.agents import AGENT_CLASSES
    from app.database import SessionLocal
    with SessionLocal() as db:
        marc = AGENT_CLASSES["marc"].load(db, "marc")
        assert "no theme" in marc._dispatch_command("/angles")["task_title"]
        a = marc._dispatch_command("/angles stack consolidation")
        assert a["action"] == "proposed_angles" and a["metadata"]["theme"] == "stack consolidation"
        c = marc._dispatch_command("/content stack consolidation")
        assert c["action"] == "wrote_content"
        assert "[STAT TO VERIFY]" in c["augmented_message"]   # never-invent-data guardrail


# ── Maya /top glued form (finding: /top5 fell through to default 50) ────────

def test_maya_top_accepts_glued_number(client):
    from app.agents import AGENT_CLASSES
    from app.database import SessionLocal
    with SessionLocal() as db:
        maya = AGENT_CLASSES["maya"].load(db, "maya")
        meta = maya._dispatch_command("/top5")
        # task_title carries n — glued "/top5" must resolve n=5, not 50.
        assert meta["task_title"] == "Top 5 (current run)"


# ── Oliver newsletter format (70/10/20 mix, feeds MailChimp) ────────────────

def test_oliver_newsletter_is_supported(client):
    from app.agents import AGENT_CLASSES
    from app.database import SessionLocal
    with SessionLocal() as db:
        oliver = AGENT_CLASSES["oliver"].load(db, "oliver")

        # /newsletter shortcut resolves to the newsletter format
        meta = oliver._dispatch_command("/newsletter pharma commercial trends")
        assert meta["metadata"]["format"] == "newsletter"
        aug = meta["augmented_message"]
        assert "70%" in aug and "10%" in aug and "20%" in aug   # fixed mix carried
        assert "MailChimp" in aug                               # channel stated

        # /format newsletter <theme> resolves the same way
        meta2 = oliver._dispatch_command("/format newsletter Q3 medtech")
        assert meta2["metadata"]["format"] == "newsletter"

        # newsletter now listed among valid formats on an invalid type
        bad = oliver._dispatch_command("/format podcast some theme")
        assert "newsletter" in bad["augmented_message"]


# ── #16 Maya /recurring on real run history ─────────────────────────────────

def test_maya_recurring_uses_run_snapshots(client):
    from app.agents import AGENT_CLASSES
    from app.database import SessionLocal
    from app.models import RunSnapshot
    with SessionLocal() as db:
        # Big delta (0.5→9.5) so the row is guaranteed inside the capped
        # TOP RISERS section even when the real DB holds many recurring rows.
        for run, day, score in (("testrunA", 25, 0.5), ("testrunB", 26, 9.5)):
            db.add(RunSnapshot(
                import_run_id=run, company_name="Zzy Recurring Co",
                assessed_score=score,
                coverage="1 of 6", outreach_eligible=(run == "testrunB"),
                signals_found=1, run_date=datetime(2026, 5, day)))
        db.commit()
        try:
            maya = AGENT_CLASSES["maya"].load(db, "maya")
            meta = maya._dispatch_command("/recurring")
            msg = meta["augmented_message"]
            assert meta["metadata"]["runs"] >= 2
            assert "Zzy Recurring Co" in msg                 # appears across runs
            assert "0.5→9.5" in msg                          # chronological trajectory shown
        finally:
            db.query(RunSnapshot).filter(
                RunSnapshot.company_name == "Zzy Recurring Co").delete()
            db.commit()


def test_maya_recurring_trajectory_is_chronological_not_minmax(client):
    """Regression: a DECLINING company (7.5 in May → 4.6 in July) must be shown
    as 7.5→4.6 under FADERS. The old min→max display inverted every decline
    into a fake rise (4.6→7.5 ↑)."""
    from app.agents import AGENT_CLASSES
    from app.database import SessionLocal
    from app.models import RunSnapshot
    with SessionLocal() as db:
        for run, day, score in (("declA", 25, 7.5), ("declB", 26, 4.6)):
            db.add(RunSnapshot(
                import_run_id=run, company_name="Zzy Declining Co",
                assessed_score=score, coverage="1 of 6", outreach_eligible=False,
                signals_found=1, run_date=datetime(2026, 5, day)))
        db.commit()
        try:
            maya = AGENT_CLASSES["maya"].load(db, "maya")
            msg = maya._dispatch_command("/recurring")["augmented_message"]
            line = next(l for l in msg.splitlines() if "Zzy Declining Co" in l)
            assert "7.5→4.6" in line and "↓" in line          # chronological + falling
            assert "4.6→7.5" not in line                      # the inverted form
            faders = msg.split("TOP FADERS")[1].split("Stable:")[0]
            assert "Zzy Declining Co" in faders               # listed as a fader
        finally:
            db.query(RunSnapshot).filter(
                RunSnapshot.company_name == "Zzy Declining Co").delete()
            db.commit()


def test_hugo_surfaces_freshness_everywhere(client):
    """The universe mixes vintages — /stats, /scan and /company must all carry
    the per-company run date so a stale May score is never presented as live
    intelligence."""
    from app.agents import AGENT_CLASSES
    from app.database import SessionLocal
    with SessionLocal() as db:
        hugo = AGENT_CLASSES["hugo"].load(db, "hugo")

        stats = hugo._dispatch_command("/stats")
        assert "fresh" in stats["metadata"] and "Freshness:" in stats["augmented_message"]

        scan = hugo._dispatch_command("/scan")
        assert "stale" in scan["metadata"]
        assert ("latest run" in scan["augmented_message"]
                or "STALE" in scan["augmented_message"])

        rerun = hugo._dispatch_command("/rerun")
        assert set(rerun["metadata"]) >= {"live_ready", "anthropic", "research"}


def test_vera_universe_audit_dispatch(client):
    from app.agents import AGENT_CLASSES
    from app.database import SessionLocal
    with SessionLocal() as db:
        vera = AGENT_CLASSES["vera"].load(db, "vera")
        meta = vera._dispatch_command("/audit")          # no company ⇒ universe audit
        assert meta["task_title"] == "Integrity audit — universe"
        assert meta["metadata"]["total"] > 0
        assert "Duplicate company groups" in meta["augmented_message"]


def test_hugo_candidates_lists_discovery_output(client, tmp_path, monkeypatch):
    from app.agents import AGENT_CLASSES
    from app.database import SessionLocal
    import app.agents.hugo as hugo_mod
    csv_file = tmp_path / "discovery_candidates.csv"
    csv_file.write_text("Company Name,Theme,Source URL\n"
                        "Alpenpharm AG,earnings_call_digital,https://x\n"
                        "Bergbio,pe_event,https://y\n", encoding="utf-8")
    monkeypatch.setattr(hugo_mod, "DISCOVERY_CSV", csv_file)
    with SessionLocal() as db:
        hugo = AGENT_CLASSES["hugo"].load(db, "hugo")
        meta = hugo._dispatch_command("/candidates")
        assert meta["metadata"]["candidates"] == 2
        assert "Alpenpharm AG" in meta["augmented_message"]
        assert "HUMAN" in meta["augmented_message"]      # review-before-spend framing

        monkeypatch.setattr(hugo_mod, "DISCOVERY_CSV", tmp_path / "absent.csv")
        none = hugo._dispatch_command("/candidates")
        assert "none yet" in none["task_title"]


def test_traceability_runs_api_and_downloads(client):
    r = client.get("/api/runs")
    assert r.status_code == 200
    d = r.json()
    assert d["count"] >= 1
    run = d["runs"][0]                                    # newest first
    for k in ("run_id", "run_date", "companies", "eligible", "hugo_recap",
              "maya_recap", "hugo_csv", "maya_csv"):
        assert k in run
    assert run["eligible"] <= run["companies"]            # sane counts
    assert "Hugo scored" in run["hugo_recap"]
    assert run["maya_recap"].startswith("Maya")
    # downloads are real CSV attachments
    h = client.get(run["hugo_csv"])
    assert h.status_code == 200 and "text/csv" in h.headers["content-type"]
    assert "attachment; filename=" in h.headers["content-disposition"]
    assert h.text.splitlines()[0] == "Company,Assessed Score,Coverage,Outreach Eligible,Signals Found"
    m = client.get(run["maya_csv"])
    assert m.status_code == 200 and "Trajectory" in m.text.splitlines()[0]
    # combined Hugo x Maya CSV = both agents side by side
    comb = client.get(run["combined_csv"])
    assert comb.status_code == 200
    head = comb.text.splitlines()[0]
    assert "Hugo — Score" in head and "Maya — Movement" in head
    # folder export writes a bundle
    exp = client.post(f"/api/runs/{run['run_id']}/export").json()
    assert exp["ok"] and exp["files"] == 4 and "agent_results" in exp["folder"]
    # sharepoint link is exposed
    assert client.get("/api/runs").json()["sharepoint_url"].startswith("https://")
    # page renders
    assert client.get("/runs").status_code == 200


def test_maya_shortlist_is_threshold_banded_not_fixed_count(client):
    """The actionable shortlist is score-gated (≥8 = ACT NOW, 5-7 = MONITOR),
    never padded to a fixed 50 with weak scores."""
    from app.agents import AGENT_CLASSES
    from app.database import SessionLocal
    with SessionLocal() as db:
        maya = AGENT_CLASSES["maya"].load(db, "maya")
        meta = maya._dispatch_command("/shortlist")
    m = meta["metadata"]
    assert meta["action"] == "built_shortlist"
    assert "ACT NOW" in meta["augmented_message"] and "MONITOR BENCH" in meta["augmented_message"]
    # eligible band is capped at the soft cap; monitor is separate
    assert m["eligible"] <= 40 or m["capped"]
    assert isinstance(m["monitor"], int)
    # honesty: never claims a fixed count
    assert "top 50" not in meta["augmented_message"].lower()
