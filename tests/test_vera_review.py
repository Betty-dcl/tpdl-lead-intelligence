"""Vera (9th agent) + human-review queue — offline tests, no API calls."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


MARKER = "Zzy Vera Test Co"


@pytest.fixture()
def flagged_company():
    """Insert a review-flagged company with one weak signal; clean up after."""
    from app.database import SessionLocal
    from app.models import Company, Signal
    with SessionLocal() as db:
        db.query(Signal).filter(Signal.company_name == MARKER).delete()
        db.query(Company).filter(Company.name == MARKER).delete()
        db.commit()
        db.add(Company(name=MARKER, sector_bucket="Pharma", assessed_score=8.5,
                       coverage="1 of 6", outreach_eligible=True, signals_found=1,
                       review_flag=True, review_flag_reason="high confidence but no source"))
        db.add(Signal(company_name=MARKER, slot=1, category="pe_event",
                      what_happened="Acme is reportedly in talks to be acquired.",
                      why_it_matters="PE pressure.", confidence="high",
                      sources="", urls=""))
        db.commit()
    yield MARKER
    with SessionLocal() as db:
        db.query(Signal).filter(Signal.company_name == MARKER).delete()
        db.query(Company).filter(Company.name == MARKER).delete()
        db.commit()


# ── audit_signals (pure) ────────────────────────────────────────────────────

def test_audit_signals_finds_issues():
    from app.agents.vera import audit_signals
    from app.models import Signal
    s = Signal(company_name="X", slot=1, category="pe_event",
               what_happened="reportedly in talks to acquire a rival",
               why_it_matters="BOILER", confidence="high", sources="", urls="")
    issues = audit_signals([s], boilerplate_rationales={"BOILER"})
    joined = " | ".join(issues).lower()
    assert "no verifiable source url" in joined      # high confidence, no URL
    assert "speculative" in joined                    # "reportedly / in talks"
    assert "boilerplate" in joined                    # rationale reused


def test_audit_signals_clean_when_sourced():
    from app.agents.vera import audit_signals
    from app.models import Signal
    s = Signal(company_name="X", slot=1, category="leadership_change",
               what_happened="Anna Roe was appointed CEO on 1 June 2026.",
               why_it_matters="unique", confidence="high",
               sources="serper_news", urls="https://news.example/x")
    assert audit_signals([s], boilerplate_rationales=set()) == []


# ── Vera dispatch ───────────────────────────────────────────────────────────

def test_vera_registered_and_commands(client, flagged_company):
    from app.agents import AGENT_CLASSES
    from app.database import SessionLocal
    assert "vera" in AGENT_CLASSES
    with SessionLocal() as db:
        vera = AGENT_CLASSES["vera"].load(db, "vera")
        review = vera._dispatch_command("/review")
        audit = vera._dispatch_command(f"/audit {flagged_company}")
        stats = vera._dispatch_command("/stats")
    assert review and flagged_company in review["augmented_message"]
    assert audit and audit["metadata"]["verdict"] == "NEEDS REVIEW"
    assert "no verifiable source" in audit["augmented_message"].lower()
    assert stats and stats["metadata"]["flagged"] >= 1


def test_vera_in_roster_and_profile(client):
    ids = {a["id"] for a in client.get("/api/agents").json()}
    assert "vera" in ids
    assert client.get("/agent/vera").status_code == 200


# ── Review API ──────────────────────────────────────────────────────────────

def test_review_list_and_decision_roundtrip(client, flagged_company):
    # appears in pending
    pending = client.get("/api/review?status=pending").json()
    assert any(i["name"] == flagged_company for i in pending["items"])

    # record an approval
    r = client.post(f"/api/review/{flagged_company}",
                    json={"decision": "approved", "note": "checked source manually"})
    assert r.status_code == 200 and r.json()["review_status"] == "approved"

    # now gone from pending, present in reviewed with the note
    assert not any(i["name"] == flagged_company
                   for i in client.get("/api/review?status=pending").json()["items"])
    reviewed = client.get("/api/review?status=reviewed").json()["items"]
    row = next(i for i in reviewed if i["name"] == flagged_company)
    assert row["review_status"] == "approved" and row["reviewed_note"] == "checked source manually"


def test_review_decision_validation(client, flagged_company):
    assert client.post(f"/api/review/{flagged_company}",
                       json={"decision": "maybe"}).status_code == 422
    assert client.post("/api/review/Zzz-Nonexistent-Co-999",
                       json={"decision": "approved"}).status_code == 404


def test_review_page_renders(client):
    res = client.get("/review")
    assert res.status_code == 200 and "reviewPage" in res.text
