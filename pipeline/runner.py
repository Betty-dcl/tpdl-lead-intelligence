"""The engine runner — orchestrates steps 0→6 for one or more companies.

    DRY-RUN (default, zero cost):
        python -m pipeline.runner --fixture pipeline/fixtures/probe_diagnostics.json
    LIVE (spends money — requires keys + explicit flag):
        python -m pipeline.runner --company "Straumann Group" --live

Output: a scored_results-compatible CSV (default data/csv/engine_run.csv),
re-importable via `python import_csv.py <path>`.
"""
from __future__ import annotations

import argparse
import json
import logging
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from pipeline import export, extract, research, score, techscan
from pipeline.config import EngineConfig
from pipeline.types import CompanyResult

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] [%(name)s] %(message)s")
logger = logging.getLogger("pipeline.runner")

DEFAULT_OUT = Path("data/csv/engine_run.csv")


def run_company(cfg: EngineConfig, name: str, sector: str | None = None,
                fixture: Path | None = None,
                identity: dict | None = None) -> CompanyResult:
    """Steps 1→5 for a single company. (Step 0 = caller supplies the identity;
    step 5 Batch API comes with milestone M7 — sequential calls until then.)"""
    identity = identity or {}

    # Step 1 — tech scan (Apify/Wappalyzer). A pre-supplied summary wins;
    # otherwise scan the domain (live) or mock it (dry-run). no_tech_detected
    # and scan_blocked are themselves commercial signals (Neotek spec §8).
    tech_stack = identity.get("tech_stack_summary")
    if not tech_stack:
        domain = identity.get("website")
        ts = techscan.scan(cfg, domain, identity.get("technologies"))
        tech_stack = ts.summary()
        logger.info("[%s] tech scan: %s", name,
                    "digital gap (no CRM)" if ts.is_digital_gap()
                    else "blocked" if ts.scan_blocked
                    else "no domain" if ts.domain_missing else "stack detected")

    # Step 2 — research: raw docs (fixture in dry-run, live sources otherwise)
    docs = research.gather(cfg, name, fixture=fixture)
    logger.info("[%s] research: %d raw docs", name, len(docs))

    # Step 3 — extraction (Sonnet 5) + verbatim QA in code
    block, violations = extract.extract(cfg, name, sector, docs, tech_stack)
    logger.info("[%s] extraction: %d evidence items (%d verbatim violations dropped)",
                name, len(block.items), len(violations))

    # Step 4 — interpretation (Opus 4.8) + deterministic scoring
    scored, not_evidenced, summary = score.interpret_and_score(cfg, block)
    flag, reason = score.review_flag(scored)
    if violations:
        flag, reason = True, "; ".join(filter(None, [reason, f"{len(violations)} extraction QA violations"]))

    result = CompanyResult(
        name=name,
        sector=sector,
        website=identity.get("website"),
        location=identity.get("location"),
        revenue=identity.get("revenue"),
        intelligence_summary=summary,
        signals=scored,
        signals_not_evidenced=not_evidenced,
        tech_stack_summary=tech_stack,
        historical_context=identity.get("historical_context"),
        icp_flag=bool(identity.get("icp_flag", False)),
        review_flag=flag,
        review_flag_reason=reason,
        run_date=datetime.now(timezone.utc).isoformat(),
    )
    logger.info("[%s] scored: %.1f (%s) — outreach %s", name, result.assessed_score,
                result.coverage, result.outreach_eligible(cfg.outreach_threshold))
    return result


def flag_boilerplate(results: list[CompanyResult]) -> None:
    """Cross-company review flag: identical tpdl rationale on 3+ companies."""
    rationales = Counter()
    for r in results:
        for s in r.signals:
            if s.signal.why_it_matters:
                rationales[s.signal.why_it_matters] += 1
    boilerplate = {text for text, n in rationales.items() if n >= 3}
    if not boilerplate:
        return
    for r in results:
        if any(s.signal.why_it_matters in boilerplate for s in r.signals):
            r.review_flag = True
            extra = "boilerplate tpdl_rationale shared by 3+ companies"
            r.review_flag_reason = "; ".join(filter(None, [r.review_flag_reason, extra]))


def _select_companies(args) -> list:
    """Resolve the run's company list (Step 0). Fixture/--company stay
    standalone; --top/--lunch/--names read the dashboard DB."""
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


def main() -> None:
    parser = argparse.ArgumentParser(description="TPDL Lead Intelligence engine")
    # ── company selection (Step 0) ──
    parser.add_argument("--company", help="Single company name")
    parser.add_argument("--sector", default=None)
    parser.add_argument("--fixture", type=Path, default=None,
                        help="JSON fixture → dry-run research for that company")
    parser.add_argument("--top", type=int, default=0,
                        help="Top N companies from the DB (by assessed_score)")
    parser.add_argument("--lunch", action="store_true",
                        help="Lunch Campaign pool (Switzerland + Spain radar)")
    parser.add_argument("--names", default=None,
                        help='Explicit list from the DB: --names "UCB; Straumann Group"')
    parser.add_argument("--min-score", type=float, default=0.0,
                        help="Filter for --top/--lunch (e.g. 8.0 = outreach-eligible)")
    # ── modes ──
    parser.add_argument("--estimate", action="store_true",
                        help="Print the pre-flight cost estimate and exit (spends nothing)")
    parser.add_argument("--live", action="store_true",
                        help="SPENDS MONEY: enable real API calls (needs keys in .env)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    companies = _select_companies(args)
    if not companies:
        parser.error("select companies: --company / --fixture / --top N / --lunch / --names")

    # ── pre-flight estimate: cost preview + live SerpAPI quota check ──
    if args.estimate:
        from pipeline import estimate as est_mod
        est = est_mod.estimate_run(len(companies))
        print(f"Selected companies ({len(companies)}): "
              + ", ".join(c.name for c in companies[:8])
              + ("…" if len(companies) > 8 else ""))
        print(est_mod.render(est, est_mod.serp_quota_check(est)))
        return

    cfg = EngineConfig.load(live=args.live)
    mode = "LIVE (spending enabled)" if cfg.live else "DRY-RUN (zero cost)"
    logger.info("Engine mode: %s · extraction=%s · interpretation=%s",
                mode, cfg.extraction_model, cfg.interpretation_model)

    results = [
        run_company(cfg, c.name, c.sector, fixture=args.fixture, identity=c.identity)
        for c in companies
    ]

    flag_boilerplate(results)
    out = export.write_csv(results, cfg, args.out)
    logger.info("Wrote %s (%d companies) — re-import with: python import_csv.py %s",
                out, len(results), out)


if __name__ == "__main__":
    main()
