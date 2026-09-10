"""Mega-cap trend synthesis (pipeline/recap_trends.py) — fixture-driven, no
live calls. The one thing this module MUST get right: a summary citing a
quote that isn't actually in the facts it was given must never be stored.
"""
from __future__ import annotations

from pipeline import recap_trends


def test_parse_trend_response_accepts_valid_json():
    text = '```json\n{"summary": "Foo.", "supporting_quotes": ["Foo happened."]}\n```'
    c = recap_trends._parse_trend_response(text)
    assert c is not None
    assert c.summary == "Foo."
    assert c.supporting_quotes == ["Foo happened."]


def test_parse_trend_response_rejects_broken_json():
    assert recap_trends._parse_trend_response("not json at all") is None


def test_parse_trend_response_rejects_missing_fields():
    assert recap_trends._parse_trend_response('{"summary": "Foo."}') is None
    assert recap_trends._parse_trend_response('{"supporting_quotes": ["x"]}') is None


def test_qa_trend_candidate_accepts_quotes_found_in_facts():
    facts = ["Company X launched Product A in March.", "Company X acquired Small Biotech Inc."]
    candidate = recap_trends.TrendCandidate(
        summary="Company X is expanding via product launches and M&A.",
        supporting_quotes=["Company X launched Product A in March.",
                           "Company X acquired Small Biotech Inc."],
    )
    verified, violations = recap_trends.qa_trend_candidate(candidate, facts)
    assert verified is not None
    assert verified.supporting_quotes == candidate.supporting_quotes
    assert violations == []


def test_qa_trend_candidate_drops_fabricated_quotes_but_keeps_real_ones():
    facts = ["Company X launched Product A in March."]
    candidate = recap_trends.TrendCandidate(
        summary="Company X launched a product.",
        supporting_quotes=["Company X launched Product A in March.",
                           "Company X also secretly cured cancer."],  # fabricated
    )
    verified, violations = recap_trends.qa_trend_candidate(candidate, facts)
    assert verified is not None
    assert verified.supporting_quotes == ["Company X launched Product A in March."]
    assert any("secretly cured cancer" in v for v in violations)


def test_qa_trend_candidate_rejects_summary_with_zero_verified_quotes():
    """The core guardrail: cited-but-fabricated evidence must discard the
    WHOLE summary, not just the bad citation."""
    facts = ["Company X launched Product A in March."]
    candidate = recap_trends.TrendCandidate(
        summary="Company X is doing something entirely unrelated.",
        supporting_quotes=["This quote does not exist anywhere in the facts."],
    )
    verified, violations = recap_trends.qa_trend_candidate(candidate, facts)
    assert verified is None
    assert any("0 verified citations" in v for v in violations)


def test_summarize_company_trend_returns_none_for_no_facts():
    from pipeline.config import EngineConfig

    cfg = EngineConfig.load(live=False)
    assert recap_trends.summarize_company_trend(cfg, "Empty Co", []) is None


def test_build_trend_prompt_includes_company_and_facts():
    prompt = recap_trends.build_trend_prompt("Acme Pharma", ["Fact one.", "Fact two."])
    assert "Acme Pharma" in prompt
    assert "Fact one." in prompt
    assert "Fact two." in prompt


def test_write_trend_summary_roundtrip():
    from app.database import SessionLocal
    from app.models import MegaCapTrendSummary

    candidate = recap_trends.TrendCandidate(
        summary="Test summary.", supporting_quotes=["Fact one."],
    )
    with SessionLocal() as db:
        recap_trends.write_trend_summary(db, "__Test Trend Co__", candidate, 1, "test-model")
        row = (db.query(MegaCapTrendSummary)
               .filter(MegaCapTrendSummary.company_name == "__Test Trend Co__").first())
        try:
            assert row is not None
            assert row.summary_text == "Test summary."
            import json
            assert json.loads(row.supporting_quotes) == ["Fact one."]
            assert row.facts_considered == 1
        finally:
            db.query(MegaCapTrendSummary).filter(
                MegaCapTrendSummary.company_name == "__Test Trend Co__").delete()
            db.commit()
