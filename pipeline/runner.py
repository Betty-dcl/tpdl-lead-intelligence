"""The engine runner — orchestrates steps 0→6 for one or more companies.

    DRY-RUN (default, zero cost):
        python -m pipeline.runner --fixture pipeline/fixtures/probe_diagnostics.json
    LIVE (spends money — requires keys + explicit flag):
        python -m pipeline.runner --company "Straumann Group" --live
    VOLUME (many companies, -50% via Batch API):
        python -m pipeline.runner --top 100 --live --batch
    RESUME a crashed run (skips companies already in --out):
        python -m pipeline.runner --top 100 --live --resume
    RECAP a fixed mega-cap watch-list (verbatim facts only, never scored):
        python -m pipeline.runner --recap --names "Pfizer;Sanofi;Merck" --live

Output: a scored_results-compatible CSV (default data/csv/engine_run.csv),
re-importable via `python import_csv.py <path>`. In sequential mode the CSV is
rewritten after every company, so a crash still leaves a valid partial file
(use --resume to continue). In --batch mode the companies are prepared then
scored in one call, so the CSV is written once at the end — a crash mid-prepare
loses that run's work (re-run; nothing was charged until the batch was submitted).
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import re
from datetime import date, datetime, timezone
from pathlib import Path

from app.tools import icp as _icp
from pipeline import export, extract, research, score, techscan
from pipeline.config import EngineConfig
from pipeline.types import CompanyResult, EvidenceBlock, EvidenceItem

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] [%(name)s] %(message)s")
logger = logging.getLogger("pipeline.runner")

DEFAULT_OUT = Path("data/csv/engine_run.csv")


def _prepare(cfg: EngineConfig, name: str, sector: str | None,
             fixture: Path | None, identity: dict
             ) -> tuple[EvidenceBlock, str | None, list[str], list[str]]:
    """Steps 1-3: tech scan → research → extraction (+ QA). No scoring yet."""
    # Step 1 — tech scan (Apify/Wappalyzer). Pre-supplied summary wins; else scan.
    tech_stack = identity.get("tech_stack_summary")
    if not tech_stack:
        ts = techscan.scan(cfg, identity.get("website"), identity.get("technologies"))
        tech_stack = ts.summary()
        logger.info("[%s] tech scan: %s", name,
                    "digital gap (no CRM)" if ts.is_digital_gap()
                    else "blocked" if ts.scan_blocked
                    else "no domain" if ts.domain_missing else "stack detected")

    # Step 2 — research (Europe-first SERP locale + conditional Firecrawl IR fetch)
    docs = research.gather(cfg, name, fixture=fixture,
                           location=identity.get("location"),
                           website=identity.get("website"))
    logger.info("[%s] research: %d raw docs", name, len(docs))

    # Step 3 — extraction (Sonnet 5) + verbatim QA + speculation flags
    block, violations, flags = extract.extract(cfg, name, sector, docs, tech_stack)
    logger.info("[%s] extraction: %d evidence items (%d dropped, %d flagged)",
                name, len(block.items), len(violations), len(flags))
    # Canary: a rich corpus that yields ZERO evidence is more likely an
    # extraction failure than a true absence (the lunch-run false zeros all
    # looked exactly like this). Flag it so a human checks instead of the
    # company silently scoring 0.
    if cfg.live and len(docs) >= 30 and not block.items:
        flags = [*flags, f"extraction anomaly: {len(docs)} research docs but 0 "
                         "evidence items — verify this is a true absence"]
        logger.warning("[%s] canary: %d docs but 0 evidence — review-flagged",
                       name, len(docs))
    return block, tech_stack, violations, flags


def _assemble(cfg: EngineConfig, name: str, sector: str | None, identity: dict,
              tech_stack: str | None, violations: list[str], flags: list[str],
              scored, not_evidenced, summary) -> CompanyResult:
    """Step 4 assembly: attach deterministic scores + review flags."""
    # Opt-in revenue enrichment (fail-open): fill an unknown revenue so the €100M
    # ICP floor can triage it. Never raises — worst case revenue stays unknown.
    _rev = (identity.get("revenue") or "").strip().lower()
    if cfg.enrich_revenue and (not _rev or _rev in {"na", "n/a", "none", "unknown", "-"}):
        from pipeline import enrich
        est = enrich.estimate_revenue(cfg, name)
        if est:
            identity = {**identity, "revenue": est}
    # Opt-in HQ-city enrichment (fail-open): fill the exact office city when
    # location carries only a country (or nothing). Never overwrites a value
    # that already names a city.
    if cfg.enrich_location:
        from pipeline import enrich
        if enrich.needs_city(identity.get("location")):
            city = enrich.estimate_hq_location(cfg, name)
            if city:
                identity = {**identity, "location": city}

    review, reason = score.review_flag(scored)
    extra = []
    if violations:
        extra.append(f"{len(violations)} extraction QA violations")
    anomalies = [f for f in flags if f.startswith("extraction anomaly")]
    extra.extend(anomalies)   # keep the anomaly text verbatim — it says what to check
    # Speculation flag, LOAD-BEARING only: flag a signal whose ENTIRE evidence
    # is hedged ("may", "reportedly", "envisage"…) — the signal rests on
    # speculation, so a human must verify the event happened. A hedge among
    # corroborated clean quotes is normal press language and must NOT flag:
    # quote-level flagging sent 53% of the first business run (34/36 flags)
    # to the review queue, which defeats the triage.
    resting = [s.signal.category for s in scored
               if s.signal.evidence
               and all(extract.has_negation(e.quote) for e in s.signal.evidence)]
    if resting:
        extra.append("signal(s) resting entirely on speculative/hedged quotes: "
                     + ", ".join(resting) + " — verify the event happened")
    # Constitution: the intelligence summary is EXACTLY 3 sentences. A summary
    # far outside that band (when signals exist) means the interpretation
    # drifted — flag it at the source instead of letting it age in the DB.
    if scored and summary:
        n_sent = len([s for s in re.split(r"(?<=[.!?])\s+", summary.strip()) if s])
        if not (2 <= n_sent <= 4):
            extra.append(f"summary format breach: {n_sent} sentences (constitution says 3)")
    if extra:
        review = True
        reason = "; ".join(filter(None, [reason, *extra]))

    icp_result = _icp.assess_icp(
        name, sector, identity.get("sector_bucket"),
        identity.get("revenue"), identity.get("location"),
        icp_ceiling_musd=cfg.icp_ceiling_musd,
    )
    result = CompanyResult(
        name=name, sector=sector,
        website=identity.get("website"),
        location=identity.get("location"),
        revenue=identity.get("revenue"),
        intelligence_summary=summary,
        signals=scored,
        signals_not_evidenced=not_evidenced,
        tech_stack_summary=tech_stack,
        historical_context=identity.get("historical_context"),
        icp_flag=icp_result["out_of_scope"],
        icp_flag_reason=icp_result["reason"],
        review_flag=review,
        review_flag_reason=reason,
        run_date=datetime.now(timezone.utc).isoformat(),
    )
    logger.info("[%s] scored: %.1f (%s) — outreach %s", name, result.assessed_score,
                result.coverage, result.outreach_eligible(cfg.outreach_threshold))
    return result


def run_company(cfg: EngineConfig, name: str, sector: str | None = None,
                fixture: Path | None = None,
                identity: dict | None = None) -> CompanyResult:
    """Synchronous single-company run (steps 1-4). Used for cran 1 + dry-run."""
    identity = identity or {}
    block, tech_stack, violations, flags = _prepare(cfg, name, sector, fixture, identity)
    scored, not_evidenced, summary = score.interpret_and_score(cfg, block)
    return _assemble(cfg, name, sector, identity, tech_stack, violations, flags,
                     scored, not_evidenced, summary)


def _run_recap(cfg: EngineConfig, companies) -> None:
    """Mega-cap trend-watch (chantier 2/4, 2026-09-01 recap): verbatim facts
    only, filed by category. NEVER calls score.interpret_and_score() — no
    Opus call, no assessed_score, no CompanyResult for this mode."""
    from app.database import SessionLocal
    from pipeline import recap

    run_date = datetime.now(timezone.utc)
    company_items: list[tuple[str, list]] = []
    with SessionLocal() as db:
        for c in companies:
            website = (c.identity or {}).get("website")
            docs = recap.gather_recap(cfg, c.name, website=website)
            items, violations = recap.extract_recap(cfg, c.name, docs)
            recap.write_recap_rows(db, c.name, run_date, items)
            company_items.append((c.name, items))
            logger.info("[recap] %s: %d recap items from %d docs (%d QA violations dropped)",
                        c.name, len(items), len(docs), len(violations))

    out_path = Path(f"data/csv/megacap_recap_{run_date.date().isoformat()}.csv")
    recap.export_recap_csv(company_items, run_date, out_path)
    logger.info("Wrote %s (%d companies, %d total recap items)",
                out_path, len(company_items), sum(len(i) for _, i in company_items))


_BOILERPLATE_MIN = 3        # a rationale shared by this many is boilerplate
_BOILERPLATE_SIM = 0.9      # Jaccard ≥ this ⇒ "the same rationale" (near-duplicate)


def _rationale_tokens(text: str) -> frozenset[str]:
    """Casefolded, punctuation-stripped token set — the comparison basis.

    Exact-string matching missed the real thing: Opus rarely repeats a rationale
    character-for-character, it drifts by a word, a capital or a comma. Comparing
    normalised token SETS catches those near-identical variants too.
    """
    return frozenset(re.sub(r"[^\w\s]", " ", text).casefold().split())


def _near_duplicate(a: frozenset[str], b: frozenset[str]) -> bool:
    """True if two rationales are the same modulo trivial wording (Jaccard ≥ 0.9).

    The threshold is deliberately strict (≤ ~2 differing words in a 20-word
    rationale) so genuinely distinct rationales are never merged."""
    if not a or not b:
        return False
    return len(a & b) / len(a | b) >= _BOILERPLATE_SIM


def flag_boilerplate(results: list[CompanyResult],
                     existing_rows: list[dict] | None = None) -> None:
    """Cross-company review flag: the same tpdl rationale (near-identical) on 3+.

    On --resume, seed the corpus from rows already written (their `Signal N Why
    It Matters` columns) so boilerplate spanning the prior + current batch is
    still caught — otherwise a rationale repeated across the resume boundary
    slips through. Matching is normalised + near-duplicate, not exact string.
    """
    corpus: list[frozenset[str]] = []
    for row in existing_rows or []:
        for col in ("Signal 1 Why It Matters", "Signal 2 Why It Matters",
                    "Signal 3 Why It Matters"):
            text = (row.get(col) or "").strip()
            if text:
                corpus.append(_rationale_tokens(text))
    for r in results:
        for s in r.signals:
            if s.signal.why_it_matters:
                corpus.append(_rationale_tokens(s.signal.why_it_matters))
    if not corpus:
        return

    def occurrences(tokens: frozenset[str]) -> int:
        # counts itself + its near-duplicates in the corpus (parity with the old
        # occurrence count, but tolerant of wording drift)
        return sum(1 for other in corpus if _near_duplicate(tokens, other))

    for r in results:
        for s in r.signals:
            wm = s.signal.why_it_matters
            if wm and occurrences(_rationale_tokens(wm)) >= _BOILERPLATE_MIN:
                r.review_flag = True
                extra = "boilerplate tpdl_rationale shared by 3+ companies"
                r.review_flag_reason = "; ".join(filter(None, [r.review_flag_reason, extra]))
                break


def _select_companies(args) -> list:
    """Resolve the run's company list (Step 0)."""
    from pipeline import loader

    if args.fixture:
        payload = json.loads(args.fixture.read_text(encoding="utf-8"))
        name = args.company or payload.get("company", "Fixture Co")
        return [loader.LoadedCompany(
            name=name,
            sector=args.sector or payload.get("sector"),
            identity={k: payload.get(k)
                      for k in ("website", "location", "revenue", "technologies")},
        )]
    if args.company:
        return [loader.LoadedCompany(name=args.company, sector=args.sector, identity={})]
    if args.names:
        return loader.load_names(args.names.split(";"))
    if args.lunch:
        return loader.load_lunch(min_score=args.min_score)
    if args.top:
        return loader.load_top(args.top, min_score=args.min_score)
    return []


def _done_names(out: Path) -> set[str]:
    """Company names already present in an existing output CSV (for --resume)."""
    if not out.exists():
        return set()
    with open(out, encoding="utf-8", newline="") as f:
        return {row["Company Name"].strip() for row in csv.DictReader(f)
                if row.get("Company Name", "").strip()}


def main() -> None:
    parser = argparse.ArgumentParser(description="TPDL Lead Intelligence engine")
    # ── company selection (Step 0) ──
    parser.add_argument("--company", help="Single company name")
    parser.add_argument("--sector", default=None)
    parser.add_argument("--fixture", type=Path, default=None)
    parser.add_argument("--top", type=int, default=0)
    parser.add_argument("--lunch", action="store_true")
    parser.add_argument("--names", default=None)
    parser.add_argument("--min-score", type=float, default=0.0)
    # ── modes ──
    parser.add_argument("--estimate", action="store_true",
                        help="Print the pre-flight cost estimate and exit (spends nothing)")
    parser.add_argument("--live", action="store_true",
                        help="SPENDS MONEY: enable real API calls (needs keys in .env)")
    parser.add_argument("--batch", action="store_true",
                        help="Score via the Anthropic Batch API (-50%%, up to 24h)")
    parser.add_argument("--submit", action="store_true",
                        help="Batch submit→exit (no 24h wait): research+extract, submit the "
                             "scoring batch, save state, then the machine can be shut down. "
                             "Collect later with --fetch. Implies --batch --live.")
    parser.add_argument("--fetch", type=Path, default=None, metavar="STATE.json",
                        help="Collect a batch submitted with --submit and write the CSV "
                             "(re-run until Anthropic has finished, within 24h).")
    parser.add_argument("--resume", action="store_true",
                        help="Skip companies already in --out (recover a crashed run)")
    parser.add_argument("--force", action="store_true",
                        help="Run even if the SerpAPI quota looks insufficient")
    parser.add_argument("--recap", action="store_true",
                        help="Mega-cap trend-watch: verbatim facts only (new "
                             "products/M&A/tech platform), NEVER scored — no "
                             "Opus call, no assessed_score. Requires --live + "
                             "--names \"A;B;C\". Writes MegaCapRecap rows + a CSV, "
                             "not a CompanyResult.")
    parser.add_argument("--discover", action="store_true",
                        help="Market-watch discovery: search the 6 signal themes + the "
                             "earnings-call angle across the broad life-science scope and "
                             "output NEW candidate companies (not yet in the universe) to "
                             "data/csv/discovery_candidates.csv. Requires --live "
                             "(thematic search + one small Sonnet call, <$0.10).")
    parser.add_argument("--enrich-revenue", action="store_true",
                        help="fill unknown revenues via 1 Perplexity call/company "
                             "(fail-open) so the €100M ICP floor can triage them")
    parser.add_argument("--enrich-location", action="store_true",
                        help="fill the head-office CITY via 1 Perplexity call/company "
                             "(fail-open) when location carries only a country")
    parser.add_argument("--no-eu-registry", action="store_true",
                        help="Disable the free public EU-registry source for this run "
                             "(default ON; saves 1 SERP search/company when quota is tight)")
    parser.add_argument("--social-scan", action="store_true",
                        help="9th source (opt-in, default OFF): Twitter/Reddit/LinkedIn-jobs/"
                             "Instagram/YouTube via agent-reach's CLIs (OpenCLI + yt-dlp, "
                             "Betty's own logged-in browser session). Free, but browser-"
                             "automation-slow and rate-limited by each platform — size runs "
                             "accordingly (shortlist/--lunch/--names, not the full universe).")
    parser.add_argument("--rescan-tech", action="store_true",
                        help="Force a fresh Apify tech scan even when the DB already "
                             "holds a tech-stack summary (default: reuse the stored "
                             "summary and spend nothing on Apify)")
    parser.add_argument("--max-usd", type=float, default=None,
                        help="Hard budget cap (USD): stop the run before the estimated "
                             "model spend would exceed this. Live runs only.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    # ── fetch a previously-submitted batch (no company selection needed) ──
    if args.fetch is not None:
        _run_fetch(EngineConfig.load(live=True), args)
        return

    # ── discovery: find NEW companies (no company selection needed) ──
    if args.discover:
        if not args.live:
            parser.error("--discover requires --live (thematic search + one Sonnet call)")
        from pipeline import discovery
        discovery.discover(EngineConfig.load(live=True))
        return

    companies = _select_companies(args)
    if not companies:
        parser.error("select companies: --company / --fixture / --top N / --lunch / --names")

    # ── recap mode: verbatim facts only, NEVER scored (own small flow) ──
    if args.recap:
        from pipeline import estimate as est_mod
        if args.estimate:
            print(f"Selected companies ({len(companies)}): "
                  + ", ".join(c.name for c in companies[:8])
                  + ("…" if len(companies) > 8 else ""))
            print(est_mod.render_recap(est_mod.estimate_recap_run(len(companies))))
            return
        if not args.live:
            parser.error("--recap requires --live (Sonnet 5 extraction, no scoring)")
        _run_recap(EngineConfig.load(live=True), companies)
        return

    # --rescan-tech: drop the stored tech-stack summary so Step 1 actually
    # scans via Apify instead of reusing the (possibly stale) DB value.
    if args.rescan_tech:
        for c in companies:
            c.identity.pop("tech_stack_summary", None)

    from pipeline import estimate as est_mod
    est = est_mod.estimate_run(len(companies))

    # ── pre-flight estimate: cost preview + live SerpAPI quota check ──
    if args.estimate:
        print(f"Selected companies ({len(companies)}): "
              + ", ".join(c.name for c in companies[:8])
              + ("…" if len(companies) > 8 else ""))
        print(est_mod.render(est, est_mod.serp_quota_check(est),
                             social_scan=args.social_scan))
        return

    # ── resume: drop companies already scored in the output file ──
    if args.resume:
        done = _done_names(args.out)
        before = len(companies)
        companies = [c for c in companies if c.name not in done]
        logger.info("Resume: %d already done, %d remaining", before - len(companies),
                    len(companies))
        if not companies:
            logger.info("Nothing to do — all selected companies already in %s", args.out)
            return

    cfg = EngineConfig.load(live=args.live)
    if args.no_eu_registry:
        cfg.eu_registry_enabled = False
    if getattr(args, "enrich_revenue", False):
        cfg.enrich_revenue = True
    if getattr(args, "enrich_location", False):
        cfg.enrich_location = True
    if getattr(args, "social_scan", False):
        cfg.social_scan_enabled = True
    mode = "LIVE (spending enabled)" if cfg.live else "DRY-RUN (zero cost)"
    logger.info("Engine mode: %s · extraction=%s · interpretation=%s",
                mode, cfg.extraction_model, cfg.interpretation_model)

    # ── quota guardrail (#10): stop before blowing the monthly SerpAPI quota ──
    if cfg.live and not args.force:
        verdict = est_mod.serp_quota_check(est)
        if verdict and "INSUFFICIENT" in verdict:
            logger.error(verdict)
            logger.error("Refusing to start (would half-finish). Shrink the run "
                         "(--top N), wait for reset, or override with --force.")
            return

    # On resume, preserve the rows already written (never overwrite prior work).
    existing_rows = export.read_existing(args.out) if args.resume else []

    # ── submit→fetch-later: submit the batch and exit (machine can shut down) ──
    if args.submit:
        if not cfg.live:
            parser.error("--submit requires --live (it submits a paid batch)")
        _run_submit(cfg, companies, args)
        return

    if args.batch and cfg.live and len(companies) > 1:
        results = _run_batched(cfg, companies, args)
        export.write_csv(results, cfg, args.out, existing_rows)
    else:
        results = _run_sequential(cfg, companies, args, existing_rows)

    flag_boilerplate(results, existing_rows)
    export.write_csv(results, cfg, args.out, existing_rows)
    logger.info("Wrote %s (%d new + %d preserved) — re-import: python import_csv.py %s",
                args.out, len(results), len(existing_rows), args.out)


def _run_sequential(cfg, companies, args, existing_rows):
    """Score one company at a time; rewrite the CSV after each (crash-safe).

    Budget circuit-breaker (#44): in live mode, stop BEFORE the estimated model
    spend would exceed --max-usd, so a run can never silently overshoot.
    """
    from pipeline import estimate as est_mod
    per_company = est_mod.estimate_run(1).per_company_usd
    # `is not None`, not truthiness: --max-usd 0 means "spend nothing", which must
    # STOP the run, not disable the cap (0.0 is falsy).
    cap = args.max_usd if (cfg.live and args.max_usd is not None) else None

    results, spent = [], 0.0
    for c in companies:
        if cap is not None and spent + per_company > cap:
            logger.warning("[budget] STOP: next company (~$%.2f) would exceed the $%.2f cap "
                           "(spent ~$%.2f on %d companies). Raise --max-usd to continue.",
                           per_company, cap, spent, len(results))
            break
        results.append(run_company(cfg, c.name, c.sector,
                                   fixture=args.fixture, identity=c.identity))
        spent += per_company
        export.write_csv(results, cfg, args.out, existing_rows)   # crash-safe snapshot
    return results


def _run_batched(cfg, companies, args):
    """Research+extract every company, then score them all in one -50% batch."""
    from pipeline import batch as batch_mod
    from pipeline import estimate as est_mod

    # Budget circuit-breaker (#44): a batch is submitted at once, so cap by
    # trimming the company list up front rather than mid-run.
    if cfg.live and args.max_usd is not None:
        per = est_mod.estimate_run(1).model_cost_batch_usd  # batch is -50%
        affordable = int(args.max_usd // per) if per else len(companies)
        if affordable < len(companies):
            logger.warning("[budget] $%.2f cap ≈ %d companies at ~$%.3f each (batch); "
                           "trimming from %d. Raise --max-usd for the full set.",
                           args.max_usd, affordable, per, len(companies))
            companies = companies[:max(0, affordable)]
        if not companies:
            logger.error("[budget] cap too low to score even one company.")
            return []

    prepared, blocks = [], []
    for c in companies:
        block, tech, viol, flags = _prepare(cfg, c.name, c.sector, args.fixture, c.identity)
        prepared.append((c, tech, viol, flags))
        blocks.append(block)
    scored_by_company = batch_mod.score_blocks_batched(cfg, blocks)
    results = []
    for c, tech, viol, flags in prepared:
        scored, not_ev, summary = scored_by_company.get(c.name, ([], [], ""))
        results.append(_assemble(cfg, c.name, c.sector, c.identity, tech, viol, flags,
                                 scored, not_ev, summary))
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Submit → fetch-later (machine-free 24h batch wait)
#   --submit : research+extract locally, submit the scoring batch, write a
#              pending-state file, EXIT. The machine can then be shut down.
#   --fetch  : read the state file, and once Anthropic has finished, collect +
#              assemble + write the CSV. Re-run until it's ready.
# ─────────────────────────────────────────────────────────────────────────────

def _block_to_dict(b: EvidenceBlock) -> dict:
    return {
        "company_name": b.company_name, "sector": b.sector,
        "tech_stack_summary": b.tech_stack_summary,
        "items": [{"quote": it.quote, "source": it.source, "url": it.url,
                   "event_date": it.event_date.isoformat() if it.event_date else None,
                   "category": it.category} for it in b.items],
    }


def _block_from_dict(d: dict) -> EvidenceBlock:
    items = [EvidenceItem(
        quote=i["quote"], source=i["source"], url=i["url"],
        event_date=date.fromisoformat(i["event_date"]) if i["event_date"] else None,
        category=i["category"]) for i in d["items"]]
    return EvidenceBlock(company_name=d["company_name"], sector=d["sector"],
                         items=items, tech_stack_summary=d["tech_stack_summary"])


def _pending_path(out: Path) -> Path:
    return out.with_suffix(out.suffix + ".pending.json")


def _run_submit(cfg, companies, args) -> None:
    """Research+extract locally, submit the scoring batch, persist state, exit."""
    from pipeline import batch as batch_mod
    from pipeline import estimate as est_mod

    if cfg.live and args.max_usd is not None:          # same budget trim as _run_batched
        per = est_mod.estimate_run(1).model_cost_batch_usd
        affordable = int(args.max_usd // per) if per else len(companies)
        if affordable < len(companies):
            logger.warning("[budget] $%.2f cap ≈ %d companies (batch); trimming from %d.",
                           args.max_usd, affordable, len(companies))
            companies = companies[:max(0, affordable)]
        if not companies:
            logger.error("[budget] cap too low to score even one company.")
            return

    prepared, blocks = [], []
    for c in companies:
        block, tech, viol, flags = _prepare(cfg, c.name, c.sector, args.fixture, c.identity)
        prepared.append((c, tech, viol, flags))
        blocks.append(block)

    batch_id = batch_mod.submit_blocks(cfg, blocks)

    state = {
        "batch_id": batch_id,
        "out": str(args.out),
        # Enrichment happens in _assemble, which for a batch runs at --fetch time.
        # Persist the flags so --fetch honours them (else the city/revenue fill is
        # silently lost for batch runs — it only worked on synchronous ones).
        "enrich_location": bool(cfg.enrich_location),
        "enrich_revenue": bool(cfg.enrich_revenue),
        "companies": [
            {"name": c.name, "sector": c.sector, "identity": c.identity,
             "tech_stack": tech, "violations": viol, "flags": flags,
             "block": _block_to_dict(block)}
            for (c, tech, viol, flags), block in zip(prepared, blocks)
        ],
    }
    pending = _pending_path(args.out)
    pending.parent.mkdir(parents=True, exist_ok=True)
    pending.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Batch %s submitted for %d companies. State saved to %s",
                batch_id, len(blocks), pending)
    logger.info("You can now shut the machine down. Later, fetch the results with:\n"
                "    python -m pipeline.runner --fetch %s", pending)


def _run_fetch(cfg, args) -> None:
    """Collect a previously-submitted batch and write the CSV (re-run until ready)."""
    from pipeline import batch as batch_mod

    pending = args.fetch
    if not pending.exists():
        logger.error("No pending-state file at %s", pending)
        return
    state = json.loads(pending.read_text(encoding="utf-8"))
    batch_id = state["batch_id"]
    # Restore the enrichment flags saved at submit time so --fetch fills the HQ
    # city / revenue in _assemble (they don't come from the CLI at fetch time).
    cfg.enrich_location = bool(state.get("enrich_location", False))
    cfg.enrich_revenue = bool(state.get("enrich_revenue", False))

    status = batch_mod.batch_status(cfg, batch_id)
    if status != "ended":
        logger.info("Batch %s not finished yet (status=%s). Try again later "
                    "(Anthropic processes within 24h).", batch_id, status)
        return

    blocks = [_block_from_dict(c["block"]) for c in state["companies"]]
    id_to_block = batch_mod._id_map(blocks)
    scored_by_company = batch_mod.collect_results(cfg, batch_id, id_to_block)

    results = []
    for c in state["companies"]:
        scored, not_ev, summary = scored_by_company.get(c["name"], ([], [], ""))
        results.append(_assemble(cfg, c["name"], c["sector"], c["identity"],
                                 c["tech_stack"], c["violations"], c["flags"],
                                 scored, not_ev, summary))

    out = Path(state["out"])
    existing_rows = export.read_existing(out) if args.resume else []
    flag_boilerplate(results, existing_rows)
    export.write_csv(results, cfg, out, existing_rows)
    logger.info("Wrote %s (%d companies) — re-import: python import_csv.py %s",
                out, len(results), out)
    pending.unlink(missing_ok=True)     # consumed


if __name__ == "__main__":
    main()
