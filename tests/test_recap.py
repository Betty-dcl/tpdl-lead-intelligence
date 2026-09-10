"""Mega-cap trend-watch (pipeline/recap.py) — fixture-driven, no live calls.

Chantier 2/4 of the 2026-09-01 Nathalie meeting recap (.claude/state.md).
Mirrors the verbatim-lock/fail-open testing style of tests/test_engine.py and
tests/test_social_research.py.
"""
from __future__ import annotations

import pytest

from pipeline import recap
from pipeline.config import EngineConfig, EngineOffline
from pipeline.types import RecapItem, RawDoc


def _doc(text="q", source="s", url="https://x", title=""):
    return RawDoc(source=source, url=url, title=title, text=text)


def _recap_item(quote="q", source="s", url="https://x", category="new_product", event_date=None):
    return RecapItem(quote=quote, source=source, url=url, event_date=event_date, category=category)


# ─────────────────────────────────────────────────────────────────────────────
# verbatim_qa_recap — same anti-hallucination contract as extract.verbatim_qa
# ─────────────────────────────────────────────────────────────────────────────

def test_verbatim_qa_recap_accepts_exact_and_rejects_paraphrase():
    docs = [_doc(text="The company launched a new drug in March 2026.", source="s")]
    good = _recap_item(quote="The company launched a new drug in March 2026.", source="s")
    paraphrase = _recap_item(quote="A new drug was launched by the company.", source="s")
    accepted, violations = recap.verbatim_qa_recap([good, paraphrase], docs)
    assert accepted == [good]
    assert any("NOT VERBATIM" in v for v in violations)


def test_verbatim_qa_recap_flags_source_mismatch_but_keeps_the_quote():
    docs = [_doc(text="Real quote here.", source="serper_news"),
           _doc(text="Other doc.", source="exa_q1")]
    misattributed = _recap_item(quote="Real quote here.", source="exa_q1")  # wrong declared source
    accepted, violations = recap.verbatim_qa_recap([misattributed], docs)
    assert accepted == [misattributed]  # real sentence, kept
    assert any("SOURCE MISMATCH" in v for v in violations)


def test_verbatim_qa_recap_rejects_unknown_category():
    docs = [_doc(text="Some fact.", source="s")]
    bad = _recap_item(quote="Some fact.", source="s", category="hiring")  # scored-pipeline category, not a recap one
    accepted, violations = recap.verbatim_qa_recap([bad], docs)
    assert accepted == []
    assert any("malformed" in v for v in violations)


# ─────────────────────────────────────────────────────────────────────────────
# mock_extract_recap — dry-run stand-in, zero cost
# ─────────────────────────────────────────────────────────────────────────────

def test_mock_extract_recap_classifies_by_category():
    docs = [_doc(
        text=("The company announced the launch of a new approved product. "
              "It also completed the acquisition of a smaller biotech firm."),
        source="serper_news",
    )]
    items = recap.mock_extract_recap("Mega Pharma Co", docs)
    cats = {it.category for it in items}
    assert "new_product" in cats
    assert "ma_activity" in cats
    # every quote is an exact substring of the source doc (verbatim by construction)
    for it in items:
        assert it.quote in docs[0].text


def test_recap_categories_include_2026_09_07_split_out_from_other():
    """The 2026-09-07 audit of the first live run found "other" holding 49/329
    facts (meant to stay small) with 3 clearly recurring patterns buried in
    it — this locks in that those categories actually exist in the taxonomy,
    not just in the prompt doc."""
    from pipeline.types import RECAP_CATEGORIES

    for cat in ("capacity_investment", "leadership_change", "legal_regulatory", "restructuring"):
        assert cat in RECAP_CATEGORIES
    assert len(RECAP_CATEGORIES) == 8


def test_mock_extract_recap_classifies_the_2026_09_07_new_categories():
    docs = [_doc(
        text=("The company invested $2 billion in a new manufacturing campus. "
              "The board elected a new chief executive officer. "
              "The company reached a settlement in ongoing litigation. "
              "The company announced layoffs as part of a cost-cutting plan."),
        source="serper_news",
    )]
    items = recap.mock_extract_recap("Mega Pharma Co", docs)
    cats = {it.category for it in items}
    assert "capacity_investment" in cats
    assert "leadership_change" in cats
    assert "legal_regulatory" in cats
    assert "restructuring" in cats
    for it in items:
        assert it.quote in docs[0].text


# ─────────────────────────────────────────────────────────────────────────────
# ir_sources — investor-subpath sweep, fail-open
# ─────────────────────────────────────────────────────────────────────────────

def test_ir_sources_tries_subpaths_in_order_and_stops_at_first_hit(monkeypatch):
    calls = []

    def fake_firecrawl_fetch(cfg, url):
        calls.append(url)
        if url.endswith("/investor-relations"):
            return [_doc(text="IR content", source="ir_fetch", url=url)]
        return []

    monkeypatch.setattr(recap.research, "firecrawl_fetch", fake_firecrawl_fetch)
    cfg = EngineConfig(live=True, firecrawl_api_key="k")
    docs = recap.ir_sources(cfg, "example.com")
    assert len(docs) == 1 and docs[0].text == "IR content"
    # tried /investors first (miss), then /investor-relations (hit) — stopped there
    assert calls[:2] == ["https://example.com/investors", "https://example.com/investor-relations"]


def test_ir_sources_fail_open_when_everything_misses(monkeypatch):
    monkeypatch.setattr(recap.research, "firecrawl_fetch", lambda cfg, url: [])
    cfg = EngineConfig(live=True, firecrawl_api_key="k")
    assert recap.ir_sources(cfg, "example.com") == []


def test_ir_sources_no_website_returns_empty():
    cfg = EngineConfig(live=True, firecrawl_api_key="k")
    assert recap.ir_sources(cfg, None) == []


# ─────────────────────────────────────────────────────────────────────────────
# financial_statement_query — Perplexity Sonar, recap-specific wording
# ─────────────────────────────────────────────────────────────────────────────

def test_financial_statement_query_requires_live():
    dry = EngineConfig(live=False, perplexity_api_key="k")
    with pytest.raises(EngineOffline):
        recap.financial_statement_query(dry, "Mega Pharma Co")


def test_financial_statement_query_wording_and_none_found(monkeypatch):
    captured = {}

    def fake_post_json(url, payload, headers):
        captured["payload"] = payload
        return {"choices": [{"message": {"content": "none found"}}]}

    monkeypatch.setattr(recap.research, "_post_json", fake_post_json)
    cfg = EngineConfig(live=True, perplexity_api_key="k")
    docs = recap.financial_statement_query(cfg, "Mega Pharma Co")
    assert docs == []  # "none found" ⇒ no doc
    content = captured["payload"]["messages"][0]["content"]
    assert "annual report" in content and "Mega Pharma Co" in content


# ─────────────────────────────────────────────────────────────────────────────
# gather_recap — fail-open: one source erroring never takes down the others
# ─────────────────────────────────────────────────────────────────────────────

def test_gather_recap_is_fail_open(monkeypatch):
    monkeypatch.setattr(recap.research, "serp_news",
                        lambda cfg, company, **kw: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(recap.research, "exa_search",
                        lambda cfg, company: [_doc(text="ok", source="exa_q1")])
    monkeypatch.setattr(recap, "ir_sources", lambda cfg, website: [])
    monkeypatch.setattr(recap, "financial_statement_query",
                        lambda cfg, company: (_ for _ in ()).throw(RuntimeError("boom")))
    cfg = EngineConfig(live=True)
    docs = recap.gather_recap(cfg, "Mega Pharma Co")
    assert len(docs) == 1 and docs[0].text == "ok"   # survives 2 broken sources


# ─────────────────────────────────────────────────────────────────────────────
# summarize_item — deterministic, non-LLM
# ─────────────────────────────────────────────────────────────────────────────

def test_summarize_item_unconfirmed_prefix_on_hedged_quote():
    clean = _recap_item(quote="The company launched Product X.", category="new_product")
    hedged = _recap_item(quote="The company may launch Product X next year.", category="new_product")
    assert not recap.summarize_item(clean).startswith("[unconfirmed]")
    assert recap.summarize_item(hedged).startswith("[unconfirmed]")
    # No redundant "[category]" text baked in — category is its own DB column
    # and the dashboard already groups/badges facts by it (2026-09-07 fix).
    assert "[new_product]" not in recap.summarize_item(clean)
    assert recap.summarize_item(clean) == "The company launched Product X."


# ─────────────────────────────────────────────────────────────────────────────
# write_recap_rows / export_recap_csv — DB + CSV round-trip
# ─────────────────────────────────────────────────────────────────────────────

def test_write_recap_rows_and_export_csv_roundtrip(tmp_path):
    from datetime import datetime, timezone
    from app.database import SessionLocal
    from app.models import MegaCapRecap

    items = [
        _recap_item(quote="Launched Product Z in 2026.", category="new_product", source="serper_news"),
        _recap_item(quote="Acquired Small Biotech Inc.", category="ma_activity", source="exa_q1"),
    ]
    run_date = datetime.now(timezone.utc)
    company = "__Test Mega Pharma Co__"   # unlikely to collide with real data

    try:
        with SessionLocal() as db:
            n = recap.write_recap_rows(db, company, run_date, items)
            assert n == 2
            rows = db.query(MegaCapRecap).filter(MegaCapRecap.company_name == company).all()
            assert len(rows) == 2
            assert {r.category for r in rows} == {"new_product", "ma_activity"}

        out = recap.export_recap_csv([(company, items)], run_date, tmp_path / "recap.csv")
        content = out.read_text(encoding="utf-8")
        assert "Launched Product Z in 2026." in content
        assert company in content
    finally:
        with SessionLocal() as db:
            db.query(MegaCapRecap).filter(MegaCapRecap.company_name == company).delete()
            db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# CLI — money gate (mirrors test_cli_discover_requires_live)
# ─────────────────────────────────────────────────────────────────────────────

def test_cli_recap_requires_live(monkeypatch):
    """--recap without --live must refuse before any code runs (money gate)."""
    import sys
    from pipeline import runner
    monkeypatch.setattr(sys, "argv", ["runner", "--recap", "--names", "Pfizer"])
    with pytest.raises(SystemExit):
        runner.main()


def test_estimate_recap_run_has_no_opus_cost():
    from pipeline import estimate as est_mod
    est = est_mod.estimate_recap_run(10)
    assert est.companies == 10
    assert est.model_cost_usd > 0
    # sanity: recap (extraction-only) must cost less per company than the
    # scored pipeline (extraction + Opus scoring)
    scored = est_mod.estimate_run(10)
    assert est.per_company_usd < scored.per_company_usd
    assert "no Opus" in est_mod.render_recap(est)
