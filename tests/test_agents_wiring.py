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
