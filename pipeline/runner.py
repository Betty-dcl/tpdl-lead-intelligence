"""The engine runner — orchestrates steps 0→6 for one or more companies.

    DRY-RUN (default, zero cost):
        python -m pipeline.runner --fixture pipeline/fixtures/probe_diagnostics.json
    LIVE (spends money — requires keys + explicit flag):
        python -m pipeline.runner --company "Straumann Group" --live
    VOLUME (many companies, -50% via Batch API):
        python -m pipeline.runner --top 100 --live --batch
    RESUME a crashed run (skips companies already in --out):
        python -m pipeline.runner --top 100 --live --resume

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
from datetime import datetime, timezone
from pathlib import Path

from pipeline import export, extract, research, score, techscan
from pipeline.config import EngineConfig
from pipeline.types import CompanyResult, EvidenceBlock

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

    # Step 2 — research
    docs = research.gather(cfg, name, fixture=fixture)
    logger.info("[%s] research: %d raw docs", name, len(docs))

    # Step 3 — extraction (Sonnet 5) + verbatim QA + speculation flags
    block, violations, flags = extract.extract(cfg, name, sector, docs, tech_stack)
    logger.info("[%s] extraction: %d evidence items (%d dropped, %d flagged)",
                name, len(block.items), len(violations), len(flags))
    return block, tech_stack, violations, flags


def _assemble(cfg: EngineConfig, name: str, sector: str | None, identity: dict,
              tech_stack: str | None, violations: list[str], flags: list[str],
              scored, not_evidenced, summary) -> CompanyResult:
    """Step 4 assembly: attach deterministic scores + review flags."""
    review, reason = score.review_flag(scored)
    extra = []
    if violations:
        extra.append(f"{len(violations)} extraction QA violations")
    if flags:
        extra.append(f"{len(flags)} speculative/negated quote(s) — verify event happened")
    if extra:
        review = True
        reason = "; ".join(filter(None, [reason, *extra]))

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
        icp_flag=bool(identity.get("icp_flag", False)),
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
    parser.add_argument("--resume", action="store_true",
                        help="Skip companies already in --out (recover a crashed run)")
    parser.add_argument("--force", action="store_true",
                        help="Run even if the SerpAPI quota looks insufficient")
    parser.add_argument("--max-usd", type=float, default=None,
                        help="Hard budget cap (USD): stop the run before the estimated "
                             "model spend would exceed this. Live runs only.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    companies = _select_companies(args)
    if not companies:
        parser.error("select companies: --company / --fixture / --top N / --lunch / --names")

    from pipeline import estimate as est_mod
    est = est_mod.estimate_run(len(companies))

    # ── pre-flight estimate: cost preview + live SerpAPI quota check ──
    if args.estimate:
        print(f"Selected companies ({len(companies)}): "
              + ", ".join(c.name for c in companies[:8])
              + ("…" if len(companies) > 8 else ""))
        print(est_mod.render(est, est_mod.serp_quota_check(est)))
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


if __name__ == "__main__":
    main()
