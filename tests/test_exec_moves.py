"""Executive moves — discovery/extraction/storage (pipeline/exec_moves.py),
chantier 4/4 Slice 1. Fixture-driven, no live network calls."""
from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from pipeline import exec_moves
from pipeline.config import EngineConfig, EngineOffline
from pipeline.types import ExecMoveCandidate, RawDoc


def _cand(person="Jane Doe", title="Chief Medical Officer", company="Acme Pharma",
         quote="q", source="serper_news_moves", url="https://x"):
    return ExecMoveCandidate(person_name=person, new_title=title, new_company=company,
                             quote=quote, source=source, url=url)


def _doc(text="q", source="serper_news_moves", url="https://x", title=""):
    return RawDoc(source=source, url=url, title=title, text=text)


# ─────────────────────────────────────────────────────────────────────────────
# Discovery — industry-wide query, fail-open
# ─────────────────────────────────────────────────────────────────────────────

def test_press_release_query_covers_expected_terms():
    q = exec_moves.press_release_query()
    assert "Chief Medical Officer" in q
    assert "appointed" in q
    assert "pharma" in q


def test_serp_press_release_search_requires_live():
    dry = EngineConfig(live=False, serper_api_key="k")
    with pytest.raises(EngineOffline):
        exec_moves.serp_press_release_search(dry, "q")


def test_discover_moves_is_fail_open(monkeypatch):
    calls = {"n": 0}

    def flaky(cfg, query, num=10):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom")
        return [_doc(text="ok", url=f"https://x/{calls['n']}")]

    monkeypatch.setattr(exec_moves, "serp_press_release_search", flaky)
    cfg = EngineConfig(live=True, serper_api_key="k")
    docs = exec_moves.discover_moves(cfg, queries=["q1", "q2"])
    assert len(docs) == 1   # first query crashed, second survived


def test_discover_moves_caps_query_count(monkeypatch):
    seen = []
    monkeypatch.setattr(exec_moves, "serp_press_release_search",
                        lambda cfg, q, num=10: (seen.append(q) or []))
    cfg = EngineConfig(live=True, serper_api_key="k")
    exec_moves.discover_moves(cfg, queries=[f"q{i}" for i in range(20)])
    assert len(seen) == exec_moves.MAX_QUERIES


# ─────────────────────────────────────────────────────────────────────────────
# verbatim_qa_moves — same anti-hallucination contract as extract.verbatim_qa
# ─────────────────────────────────────────────────────────────────────────────

def test_verbatim_qa_moves_accepts_exact_and_rejects_paraphrase():
    docs = [_doc(text="Acme Pharma is pleased to announce Jane Doe as CMO.")]
    good = _cand(quote="Acme Pharma is pleased to announce Jane Doe as CMO.")
    paraphrase = _cand(person="John Roe", quote="Jane Doe was made CMO of Acme.")
    accepted, violations = exec_moves.verbatim_qa_moves([good, paraphrase], docs)
    assert accepted == [good]
    assert any("NOT VERBATIM" in v for v in violations)


def test_verbatim_qa_moves_flags_source_mismatch_but_keeps_it():
    docs = [_doc(text="Jane Doe named CMO.", source="serper_news_moves"),
           _doc(text="Other doc.", source="exa_q1")]
    misattributed = _cand(quote="Jane Doe named CMO.", source="exa_q1")
    accepted, violations = exec_moves.verbatim_qa_moves([misattributed], docs)
    assert accepted == [misattributed]
    assert any("SOURCE MISMATCH" in v for v in violations)


def test_verbatim_qa_moves_rejects_malformed():
    docs = [_doc(text="Some fact.")]
    missing_company = ExecMoveCandidate(person_name="Jane Doe", new_title="CMO",
                                        new_company="", quote="Some fact.",
                                        source="serper_news_moves", url=None)
    accepted, violations = exec_moves.verbatim_qa_moves([missing_company], docs)
    assert accepted == []
    assert any("malformed" in v for v in violations)


def test_live_extract_moves_requires_live():
    dry = EngineConfig(live=False, anthropic_api_key="k")
    with pytest.raises(EngineOffline):
        exec_moves.live_extract_moves(dry, [])


def test_live_extract_moves_parses_a_fake_response(monkeypatch):
    monkeypatch.setattr("pipeline.usage_log.log_anthropic_call", lambda *a, **k: None)
    reply = ('{"moves": [{"person_name": "Jane Doe", "new_title": "Chief Medical Officer", '
             '"new_company": "Acme Pharma", "previous_company": null, "previous_title": null, '
             '"move_date": null, "location": null, "quote": "Acme names Jane Doe CMO.", '
             '"source": "serper_news_moves", "url": "https://x"}]}')

    class FakeMessages:
        def create(self, **kw):
            return SimpleNamespace(stop_reason="end_turn",
                                   content=[SimpleNamespace(type="text", text=reply)],
                                   usage=SimpleNamespace(input_tokens=1, output_tokens=1))

    class FakeClient:
        def __init__(self, api_key=None):
            self.messages = FakeMessages()

    import anthropic
    monkeypatch.setattr(anthropic, "Anthropic", FakeClient)
    cfg = EngineConfig(live=True, anthropic_api_key="k")
    docs = [_doc(text="Acme names Jane Doe CMO.")]
    items = exec_moves.live_extract_moves(cfg, docs)
    assert len(items) == 1
    assert items[0].person_name == "Jane Doe"
    assert items[0].new_title == "Chief Medical Officer"


# ─────────────────────────────────────────────────────────────────────────────
# compute_dedup_key — normalized, stable
# ─────────────────────────────────────────────────────────────────────────────

def test_compute_dedup_key_is_normalized_and_stable():
    a = exec_moves.compute_dedup_key("Jane Doe", "Acme Pharma", "Chief Medical Officer")
    b = exec_moves.compute_dedup_key("  JANE   DOE ", "ACME PHARMA", "chief medical officer")
    assert a == b


def test_compute_dedup_key_distinguishes_different_moves():
    a = exec_moves.compute_dedup_key("Jane Doe", "Acme Pharma", "Chief Medical Officer")
    b = exec_moves.compute_dedup_key("Jane Doe", "Other Pharma", "Chief Medical Officer")
    assert a != b


# ─────────────────────────────────────────────────────────────────────────────
# store_moves — the ICP gate (scope filter) + dedup + DB round-trip
# ─────────────────────────────────────────────────────────────────────────────

def test_store_moves_filters_out_of_scope_and_dedups():
    from app.database import SessionLocal
    from app.models import ExecutiveMove

    in_scope = _cand(person="__Test Jane Doe__", title="Chief Medical Officer",
                     company="__Test Acme Pharma__", quote="q1", url="https://x/1")
    out_of_scope = _cand(person="__Test John Roe__", title="Manager, Regulatory Affairs",
                         company="__Test Acme Pharma__", quote="q2", url="https://x/2")
    dup_of_in_scope = _cand(person="__Test Jane Doe__", title="Chief Medical Officer",
                            company="__Test Acme Pharma__", quote="q1-again", url="https://x/1b")

    try:
        with SessionLocal() as db:
            n1 = exec_moves.store_moves(db, [in_scope, out_of_scope])
            assert n1 == 1   # only the in-scope one stored
            rows = db.query(ExecutiveMove).filter(
                ExecutiveMove.person_name == "__Test Jane Doe__").all()
            assert len(rows) == 1
            assert rows[0].seniority_tier == "c_level"
            assert rows[0].role_function == "cmo"
            assert rows[0].status == "new"

            n2 = exec_moves.store_moves(db, [dup_of_in_scope])
            assert n2 == 0   # same dedup_key — not re-inserted
            rows_after = db.query(ExecutiveMove).filter(
                ExecutiveMove.person_name == "__Test Jane Doe__").all()
            assert len(rows_after) == 1
    finally:
        with SessionLocal() as db:
            db.query(ExecutiveMove).filter(
                ExecutiveMove.person_name.in_(["__Test Jane Doe__", "__Test John Roe__"])
            ).delete(synchronize_session=False)
            db.commit()


def test_store_moves_resolves_a_known_company():
    from app.database import SessionLocal
    from app.models import Company, ExecutiveMove

    company_name = "__Test Resolvable Pharma__"
    cand = _cand(person="__Test Resolved Person__", title="Chief Operating Officer",
                company=company_name, quote="q3", url="https://x/3")
    try:
        with SessionLocal() as db:
            db.add(Company(name=company_name, location="Zurich, Switzerland"))
            db.commit()
            exec_moves.store_moves(db, [cand])
            row = db.query(ExecutiveMove).filter(
                ExecutiveMove.person_name == "__Test Resolved Person__").first()
            assert row is not None
            assert row.resolved_company_name == company_name
            assert row.location == "Zurich, Switzerland"   # inherited from the resolved company
    finally:
        with SessionLocal() as db:
            db.query(ExecutiveMove).filter(
                ExecutiveMove.person_name == "__Test Resolved Person__").delete()
            db.query(Company).filter(Company.name == company_name).delete()
            db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# CLI — money gate
# ─────────────────────────────────────────────────────────────────────────────

def test_cli_exec_moves_requires_live(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["exec_moves"])
    with pytest.raises(SystemExit):
        exec_moves.main()
