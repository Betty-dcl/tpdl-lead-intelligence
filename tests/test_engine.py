"""Engine (pipeline/) regression tests — all pure/dry-run, zero API calls.

Covers the Constitution:
- deterministic formula (strength + recency + corroboration)
- assessed_score = mean over FOUND signals only
- outreach threshold from scoring_config.yaml
- verbatim lock enforced in code (QA rejects paraphrase)
- structural isolation (interpreter payload built from evidence only)
- 38-column CSV contract == import_csv.py expectations
- full dry-run chain on the fixture
"""
from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

import pytest

from pipeline import export, extract, research, score
from pipeline.config import EngineConfig, EngineOffline, require_live
from pipeline.runner import flag_boilerplate, run_company
from pipeline.types import (
    SIGNAL_CATEGORIES,
    CompanyResult,
    EvidenceBlock,
    EvidenceItem,
    InterpretedSignal,
    RawDoc,
)

FIXTURE = Path(__file__).resolve().parent.parent / "pipeline" / "fixtures" / "probe_diagnostics.json"
TODAY = date(2026, 7, 14)  # frozen: fixture dates are relative to mid-2026


@pytest.fixture()
def cfg() -> EngineConfig:
    return EngineConfig.load(live=False)


def _item(quote="q", source="s", url="https://x", event_date=None, category="hiring"):
    return EvidenceItem(quote=quote, source=source, url=url,
                        event_date=event_date, category=category)


# ─────────────────────────────────────────────────────────────────────────────
# Deterministic scoring
# ─────────────────────────────────────────────────────────────────────────────

def test_recency_bands(cfg):
    assert score.recency_points(cfg, date(2026, 6, 20), TODAY) == 2   # ≤90d
    assert score.recency_points(cfg, date(2026, 2, 1), TODAY) == 1    # 3-6 months
    assert score.recency_points(cfg, date(2025, 1, 1), TODAY) == 0    # older
    assert score.recency_points(cfg, None, TODAY) == 0                # undated
    assert score.recency_points(cfg, date(2027, 1, 1), TODAY) == 0    # future claim


def test_corroboration_bands(cfg):
    # 2 distinct domains ⇒ 2
    two_domains = [_item(source="a", url="https://siteA.com/x"),
                   _item(source="b", url="https://siteB.com/y")]
    assert score.corroboration_points(cfg, two_domains) == 2
    # 2 links on the SAME domain ⇒ still ONE source ⇒ 1
    same_domain = [_item(source="a", url="https://siteA.com/x"),
                   _item(source="b", url="https://www.siteA.com/y")]
    assert score.corroboration_points(cfg, same_domain) == 1
    # 1 anchor + Perplexity confirming ⇒ 2 (corroborates but never anchors)
    anchored_plus_pplx = [_item(source="a", url="https://siteA.com/x"),
                          _item(source="perplexity", url=None)]
    assert score.corroboration_points(cfg, anchored_plus_pplx) == 2
    # single verified URL ⇒ 1
    assert score.corroboration_points(cfg, [_item(source="a")]) == 1
    # Perplexity only, no URL anywhere ⇒ 0
    perplexity_only = [_item(source="perplexity", url=None)]
    assert score.corroboration_points(cfg, perplexity_only) == 0


def test_formula_and_strength_clamp(cfg):
    sig = InterpretedSignal(
        category="pe_event", what_happened="w", why_it_matters="y",
        tpdl_relevance="Operating model alignment", confidence="high",
        signal_strength=99,  # model misbehaves → clamped to 6
        evidence=[_item(source="a", url="https://siteA.com", event_date=date(2026, 7, 1)),
                  _item(source="b", url="https://siteB.com", event_date=date(2026, 7, 1))],
    )
    scored = score.score_signal(cfg, sig, TODAY)
    assert scored.total == 6 + 2 + 2  # clamp + recent + corroborated


def test_assessed_score_mean_over_found_only(cfg):
    r = CompanyResult(name="X")
    assert r.assessed_score == 0.0  # no signals ⇒ 0, not mean over 6 types
    s1 = score.score_signal(cfg, InterpretedSignal(
        category="hiring", what_happened="", why_it_matters="", tpdl_relevance="",
        confidence="low", signal_strength=6,
        evidence=[_item(source="a", url="https://siteA.com", event_date=date(2026, 7, 1)),
                  _item(source="b", url="https://siteB.com", event_date=date(2026, 7, 1))]), TODAY)
    s2 = score.score_signal(cfg, InterpretedSignal(
        category="pe_event", what_happened="", why_it_matters="", tpdl_relevance="",
        confidence="low", signal_strength=2, evidence=[_item(url=None, source="perplexity")]), TODAY)
    r.signals = [s1, s2]
    assert r.assessed_score == round((10 + 2) / 2, 1)  # mean over 2 found, not /6


def test_outreach_threshold_from_yaml(cfg):
    assert cfg.outreach_threshold == 8.0  # scoring_config.yaml is the source


# ─────────────────────────────────────────────────────────────────────────────
# Verbatim lock (the anti-hallucination guarantee, in code)
# ─────────────────────────────────────────────────────────────────────────────

def test_verbatim_qa_accepts_exact_and_rejects_paraphrase():
    docs = [RawDoc(source="serper_news", url="https://x", title="T",
                   text="Dr. Lena Hartmann has been appointed CEO effective 1 June 2026.")]
    good = _item(quote="Dr. Lena Hartmann has been appointed CEO effective 1 June 2026.",
                 source="serper_news", category="leadership_change")
    paraphrase = _item(quote="Lena Hartmann became the new CEO in June.",
                       source="serper_news", category="leadership_change")
    accepted, violations = extract.verbatim_qa([good, paraphrase], docs)
    assert [i.quote for i in accepted] == [good.quote]
    assert len(violations) == 1 and "NOT VERBATIM" in violations[0]


def test_verbatim_qa_is_whitespace_tolerant_only():
    docs = [RawDoc(source="s", url=None, title="",
                   text="The board said the appointment\n  marks a new chapter.")]
    reflowed = _item(quote="The board said the appointment marks a new chapter.",
                     source="s", category="leadership_change")
    accepted, violations = extract.verbatim_qa([reflowed], docs)
    assert accepted and not violations  # newlines/spacing OK — wording changes are not


def test_verbatim_qa_rejects_unknown_category():
    docs = [RawDoc(source="s", url=None, title="", text="Some sentence here.")]
    bad = _item(quote="Some sentence here.", source="s", category="product_launch")
    accepted, violations = extract.verbatim_qa([bad], docs)
    assert not accepted and violations


# ─────────────────────────────────────────────────────────────────────────────
# Structural isolation — the interpreter never sees raw text
# ─────────────────────────────────────────────────────────────────────────────

def test_evidence_payload_contains_quotes_but_not_raw_docs():
    raw = RawDoc(source="serper_news", url="https://x", title="T",
                 text="QUOTED SENTENCE HERE. UNQUOTED SECRET CONTEXT NEVER SENT.")
    block = EvidenceBlock(company_name="X", sector=None, items=[
        _item(quote="QUOTED SENTENCE HERE.", source="serper_news",
              category="hiring")])
    payload = score.evidence_payload(block)
    assert "QUOTED SENTENCE HERE." in payload
    assert "UNQUOTED SECRET CONTEXT" not in payload  # structural isolation
    assert raw.text not in payload


# ─────────────────────────────────────────────────────────────────────────────
# Money gate
# ─────────────────────────────────────────────────────────────────────────────

def test_dry_run_blocks_every_live_call(cfg):
    assert cfg.live is False
    with pytest.raises(EngineOffline):
        require_live(cfg, "some-key", "anything")
    with pytest.raises(EngineOffline):
        research.serper_news(cfg, "X")
    with pytest.raises(EngineOffline):
        research.serpapi_news(cfg, "X")
    with pytest.raises(EngineOffline):
        research.serpapi_jobs(cfg, "X")
    with pytest.raises(EngineOffline):
        extract.live_extract(cfg, "X", [])
    with pytest.raises(EngineOffline):
        score.live_interpret(cfg, EvidenceBlock(company_name="X", sector=None))


def test_serpapi_parsing_and_serp_engine_selection(monkeypatch):
    """SerpAPI client parses news/jobs payloads; gather() picks SerpAPI when
    only its key is set, and prefers Serper when both exist. No network."""
    fake_payloads = {
        "google_news": {"news_results": [
            {"title": "New CEO named", "link": "https://siteA.com/a",
             "snippet": "Anna Roe appointed CEO effective 1 June 2026.",
             "date": "06/02/2026"},
        ]},
        "google_jobs": {"jobs_results": [
            {"title": "Head of CRM", "company_name": "Probe Diagnostics AG",
             "description": "Build the unified customer data platform.",
             "share_link": "https://jobs.example/1"},
            {"title": "Head of CRM", "company_name": "Someone Else GmbH",
             "description": "irrelevant", "share_link": "https://jobs.example/2"},
        ]},
    }

    def fake_get(url):
        for engine, payload in fake_payloads.items():
            if f"engine={engine}" in url:
                return payload
        raise AssertionError(url)

    monkeypatch.setattr(research, "_get_json", fake_get)
    live_cfg = EngineConfig(live=True, serpapi_key="test-key")

    news = research.serpapi_news(live_cfg, "Probe Diagnostics AG")
    assert len(news) == 1 and news[0].source == "serpapi_news"
    assert news[0].url == "https://siteA.com/a"

    jobs = research.serpapi_jobs(live_cfg, "Probe Diagnostics AG")
    assert len(jobs) == 1  # the other company's posting is filtered out
    assert jobs[0].source == "serpapi_jobs"

    # engine selection: serpapi-only ⇒ serpapi functions; both ⇒ serper first
    only_serpapi = EngineConfig(live=False, serpapi_key="k")
    both = EngineConfig(live=False, serpapi_key="k", serper_api_key="s")
    pick = lambda c: (research.serper_news, research.serper_jobs) if c.serper_api_key \
        else (research.serpapi_news, research.serpapi_jobs)
    assert pick(only_serpapi)[0] is research.serpapi_news
    assert pick(both)[0] is research.serper_news


# ─────────────────────────────────────────────────────────────────────────────
# CSV contract — must match import_csv.py exactly
# ─────────────────────────────────────────────────────────────────────────────

def test_csv_headers_match_import_contract():
    reference = Path("data/csv/scored_results.csv")
    if reference.exists():
        with open(reference, encoding="utf-8", newline="") as f:
            expected = next(csv.reader(f))
        assert export.CSV_HEADERS == expected
    # And the fields import_csv.py reads are all present
    for col in ("Company Name", "Assessed Score", "Outreach Eligible",
                "Signal 1 Category", "Signal 3 URLs", "Review Flag Reason", "Run Date"):
        assert col in export.CSV_HEADERS
    assert len(export.CSV_HEADERS) == 38


# ─────────────────────────────────────────────────────────────────────────────
# Full dry-run chain on the fixture (the M0 acceptance test)
# ─────────────────────────────────────────────────────────────────────────────

def test_full_dry_run_chain(cfg, tmp_path):
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    result = run_company(cfg, payload["company"], payload["sector"],
                         fixture=FIXTURE,
                         identity={k: payload.get(k) for k in ("website", "location", "revenue")})

    # Evidence was found and is verbatim by construction
    assert result.signals, "fixture should produce signals"
    cats = {s.signal.category for s in result.signals}
    assert "leadership_change" in cats      # CEO doc
    assert "pe_event" in cats               # Perplexity doc
    # ISO certification doc is noise — must NOT create a signal category beyond the 6
    assert cats <= set(SIGNAL_CATEGORIES)

    # Perplexity-only signal ⇒ corroboration 0
    pe = next(s for s in result.signals if s.signal.category == "pe_event")
    assert pe.corroboration_points == 0

    # Deterministic derivations
    assert 0 < result.assessed_score <= 10
    assert result.coverage.endswith("of 6 signal types evidenced")
    assert result.intelligence_summary

    # Export → file has 38 columns and one data row
    out = tmp_path / "engine_run.csv"
    export.write_csv([result], cfg, out)
    with open(out, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert set(rows[0].keys()) == set(export.CSV_HEADERS)
    assert rows[0]["Company Name"] == payload["company"]


# ─────────────────────────────────────────────────────────────────────────────
# Robustness upgrades: dates in quotes, dedup, retry, cache, benchmark
# ─────────────────────────────────────────────────────────────────────────────

def test_date_in_text_formats():
    assert extract.date_in_text("effective 1 June 2026, she leads") == date(2026, 6, 1)
    assert extract.date_in_text("announced June 15, 2026 in Zug") == date(2026, 6, 15)
    assert extract.date_in_text("during May 2026 the group") == date(2026, 5, 1)
    assert extract.date_in_text("closed on 2026-04-30") == date(2026, 4, 30)
    assert extract.date_in_text("at the end of April") is None      # no year → never guess
    assert extract.date_in_text("raised $2026 million") is None      # number ≠ date


def test_event_date_prefers_date_stated_in_sentence():
    doc = RawDoc(source="serper_news", url="https://x.com/a", title="T",
                 published=date(2026, 6, 20),
                 text="Anna Roe has been appointed CEO effective 1 June 2026.")
    items = extract.mock_extract("X", [doc])
    assert items and items[0].event_date == date(2026, 6, 1)  # not the publish date


def test_dedupe_drops_same_url_and_same_title():
    a = RawDoc(source="serper_news", url="https://x.com/article", title="Big news", text="t1")
    b = RawDoc(source="exa_q1", url="https://x.com/article/", title="Other", text="t2")   # same URL
    c = RawDoc(source="exa_q1", url="https://y.com/other", title="Big News", text="t3")   # same title
    d = RawDoc(source="exa_q1", url="https://z.com/new", title="Fresh", text="t4")
    unique = research.dedupe([a, b, c, d])
    assert [u.url for u in unique] == ["https://x.com/article", "https://z.com/new"]


def test_post_json_retries_on_transient_errors(monkeypatch):
    import urllib.error
    calls = {"n": 0}

    def flaky(url, payload, headers):
        calls["n"] += 1
        if calls["n"] < 3:
            raise urllib.error.URLError("temporary DNS hiccup")
        return {"ok": True}

    monkeypatch.setattr(research, "_urlopen_json", flaky)
    monkeypatch.setattr(research.time, "sleep", lambda s: None)
    assert research._post_json("https://api.example", {}, {}) == {"ok": True}
    assert calls["n"] == 3


def test_research_cache_round_trip(tmp_path):
    from pipeline import cache
    docs = [RawDoc(source="serper_news", url="https://x.com/a", title="T",
                   text="Some text.", published=date(2026, 6, 1))]
    cache.save("Probe Diagnostics AG", docs, cache_dir=tmp_path)
    loaded = cache.load("Probe Diagnostics AG", cache_dir=tmp_path)
    assert loaded is not None and len(loaded) == 1
    assert loaded[0].url == "https://x.com/a"
    assert loaded[0].published == date(2026, 6, 1)
    assert cache.load("Unknown Co", cache_dir=tmp_path) is None
    assert cache.load("Probe Diagnostics AG", cache_dir=tmp_path, max_age_days=0) is None  # stale


def _bench_row(name, score_val, eligible, cats):
    row = {h: "" for h in export.CSV_HEADERS}
    row.update({"Company Name": name, "Assessed Score": str(score_val),
                "Outreach Eligible": "TRUE" if eligible else "FALSE"})
    for i, c in enumerate(cats[:3], start=1):
        row[f"Signal {i} Category"] = c
    return row


def _write_bench_csv(path, rows):
    import csv as _csv
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = _csv.DictWriter(f, fieldnames=export.CSV_HEADERS)
        w.writeheader()
        w.writerows(rows)


def test_benchmark_measures_parity(tmp_path):
    from pipeline import benchmark
    ref = tmp_path / "ref.csv"
    eng = tmp_path / "eng.csv"
    _write_bench_csv(ref, [
        _bench_row("Alpha", 9.0, True, ["pe_event", "hiring"]),
        _bench_row("Beta", 5.0, False, ["ma_expansion"]),
        _bench_row("OnlyRef", 7.0, False, []),
    ])
    _write_bench_csv(eng, [
        _bench_row("Alpha", 8.0, True, ["pe_event"]),          # Δ -1.0, missed hiring
        _bench_row("Beta", 8.5, True, ["ma_expansion"]),       # eligibility flip
        _bench_row("OnlyEngine", 3.0, False, []),
    ])
    report = benchmark.compare(eng, ref)
    assert len(report.compared) == 2
    assert report.only_in_reference == ["OnlyRef"]
    assert report.only_in_engine == ["OnlyEngine"]
    assert report.mae == round((1.0 + 3.5) / 2, 2)
    assert report.eligibility_agreement == 50.0
    alpha = next(d for d in report.compared if d.name == "Alpha")
    assert alpha.categories_missed == {"hiring"}
    beta = next(d for d in report.compared if d.name == "Beta")
    assert beta.eligible_flip == "engine-only"
    text = benchmark.render(report)
    assert "ELIGIBLE FLIP" in text and "missed: hiring" in text


def test_benchmark_reference_against_itself_is_perfect(tmp_path):
    """Sanity: the 25/05 Neotek CSV vs itself ⇒ MAE 0, 100% agreement."""
    from pipeline import benchmark
    reference = Path("data/csv/scored_results.csv")
    if not reference.exists():
        pytest.skip("reference CSV not present")
    report = benchmark.compare(reference, reference)
    assert len(report.compared) > 400
    assert report.mae == 0.0
    assert report.eligibility_agreement == 100.0
    assert report.category_recall == 100.0


# ─────────────────────────────────────────────────────────────────────────────
# Step 1 — Tech scan
# ─────────────────────────────────────────────────────────────────────────────

def test_techscan_classifies_a_detected_stack(cfg):
    from pipeline import techscan
    ts = techscan.scan(cfg, "acme.com",
                       ["Salesforce", "Marketo", "Google Analytics", "React"])
    assert ts.crm == ["Salesforce"]
    assert ts.marketing_automation == ["Marketo"]
    assert ts.analytics == ["Google Analytics"]
    assert not ts.no_tech_detected and not ts.is_digital_gap()
    assert "CRM: Salesforce" in ts.summary()


def test_techscan_no_tech_is_a_digital_gap(cfg):
    from pipeline import techscan
    ts = techscan.scan(cfg, "smallco.com")          # domain, no technologies hint
    assert ts.no_tech_detected and ts.is_digital_gap()
    assert "digital gap" in ts.summary().lower()


def test_techscan_stack_without_crm_is_a_gap(cfg):
    from pipeline import techscan
    ts = techscan.scan(cfg, "acme.com", ["Google Analytics", "WordPress"])
    assert ts.crm == [] and ts.is_digital_gap()      # analytics but no CRM
    assert "No CRM detected" in ts.summary()


def test_techscan_missing_domain(cfg):
    from pipeline import techscan
    ts = techscan.scan(cfg, None)
    assert ts.domain_missing and not ts.is_digital_gap()
    assert "not scanned" in ts.summary()


def test_techscan_live_is_gated(cfg):
    from pipeline import techscan
    with pytest.raises(EngineOffline):
        techscan.live_scan(cfg, "acme.com")          # dry-run must block live


def test_runner_populates_tech_stack_summary(cfg):
    """The fixture has a website but no technologies → digital-gap summary."""
    import json
    from pipeline.runner import run_company
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    result = run_company(cfg, payload["company"], payload["sector"], fixture=FIXTURE,
                         identity={"website": payload.get("website")})
    assert result.tech_stack_summary
    assert "digital gap" in result.tech_stack_summary.lower()


# ─────────────────────────────────────────────────────────────────────────────
# New robustness: date guardrails, negation flags, EU registry, batch gate
# ─────────────────────────────────────────────────────────────────────────────

def test_date_in_text_guardrails():
    today = date(2026, 7, 14)
    assert extract.date_in_text("deal closes January 2030", today) is None      # future
    assert extract.date_in_text("listed since January 2010", today) is None     # >5y
    # most-recent plausible date wins over stale context in the same sentence
    assert extract.date_in_text(
        "founded January 2019, new CEO appointed June 2026", today) == date(2026, 6, 1)


def test_has_negation_flags_speculation():
    assert extract.has_negation("The group is reportedly considering a sale.")
    assert extract.has_negation("She is no longer the CEO.")
    assert extract.has_negation("The company may acquire a rival.")
    assert not extract.has_negation("Anna Roe was appointed CEO on 1 June 2026.")


def test_extract_flags_speculative_quote(cfg):
    docs = [RawDoc(source="serper_news", url="https://x.com/a", title="T",
                   text="The group is reportedly considering an acquisition of a rival.")]
    block, violations, flags = extract.extract(cfg, "X", None, docs)
    assert block.items and not violations
    assert flags and "speculative" in flags[0]           # kept but flagged for review


def test_eu_registry_and_batch_are_gated(cfg):
    from pipeline import batch
    with pytest.raises(EngineOffline):
        research.eu_registry(cfg, "X")                   # dry-run blocks
    with pytest.raises(EngineOffline):
        batch.score_blocks_batched(cfg, [EvidenceBlock(company_name="X", sector=None)])


def test_resume_reads_existing_rows(cfg, tmp_path):
    """read_existing round-trips written rows so a resume never overwrites them."""
    r = CompanyResult(name="Alpha", sector="Pharma", run_date="2026-07-14")
    out = tmp_path / "run.csv"
    export.write_csv([r], cfg, out)
    rows = export.read_existing(out)
    assert len(rows) == 1 and rows[0]["Company Name"] == "Alpha"
    # writing a second company while preserving the first
    r2 = CompanyResult(name="Beta", run_date="2026-07-14")
    export.write_csv([r2], cfg, out, existing_rows=rows)
    names = {row["Company Name"] for row in export.read_existing(out)}
    assert names == {"Alpha", "Beta"}


def test_boilerplate_flags_three_identical_rationales(cfg):
    def one(name):
        sig = InterpretedSignal(
            category="hiring", what_happened="w",
            why_it_matters="SAME RATIONALE EVERYWHERE", tpdl_relevance="x",
            confidence="low", signal_strength=3, evidence=[_item()])
        return CompanyResult(name=name, signals=[score.score_signal(cfg, sig, TODAY)])
    results = [one("A"), one("B"), one("C")]
    flag_boilerplate(results)
    assert all(r.review_flag for r in results)
    assert all("boilerplate" in (r.review_flag_reason or "") for r in results)
