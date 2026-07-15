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
        for run in ("testrunA", "testrunB"):
            db.add(RunSnapshot(
                import_run_id=run, company_name="Zzy Recurring Co",
                assessed_score=7.0 if run == "testrunA" else 8.5,
                coverage="1 of 6", outreach_eligible=(run == "testrunB"),
                signals_found=1, run_date=datetime(2026, 5, 25)))
        db.commit()
        try:
            maya = AGENT_CLASSES["maya"].load(db, "maya")
            meta = maya._dispatch_command("/recurring")
            msg = meta["augmented_message"]
            assert meta["metadata"]["runs"] >= 2
            assert "Zzy Recurring Co" in msg                 # appears across runs
            assert "7.0" in msg and "8.5" in msg             # score trajectory shown
        finally:
            db.query(RunSnapshot).filter(
                RunSnapshot.company_name == "Zzy Recurring Co").delete()
            db.commit()
