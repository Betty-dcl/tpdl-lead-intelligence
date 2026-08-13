"""Pre-flight cost estimator — know what a run costs BEFORE spending a cent.

    python -m pipeline.runner --top 20 --estimate

Prints per-provider API consumption and the model bill (normal vs Batch -50%),
and — when a SerpAPI key is configured — checks the REMAINING monthly quota
via the free /account endpoint and warns if the run doesn't fit.
"""
from __future__ import annotations

from dataclasses import dataclass

# Per-company API consumption (design: 8 sources, of which live today:)
SERP_SEARCHES_PER_COMPANY = 3      # News + Jobs + EU registry (default-on)
EXA_REQUESTS_PER_COMPANY = 3       # Q1 / Q2 / Q3
PPLX_REQUESTS_PER_COMPANY = 1      # Sonar

# Model token envelopes per company (scope doc §8 — to refine after cran 1).
EXTRACT_IN_TOK, EXTRACT_OUT_TOK = 6_000, 1_000     # Sonnet 5
SCORE_IN_TOK, SCORE_OUT_TOK = 2_500, 800           # Opus 4.8

# List prices, USD per MTok.
SONNET_IN, SONNET_OUT = 2.0, 10.0   # launch price until 2026-08-31
OPUS_IN, OPUS_OUT = 5.0, 25.0
BATCH_DISCOUNT = 0.5


@dataclass
class RunEstimate:
    companies: int
    serp_searches: int
    exa_requests: int
    pplx_requests: int
    model_cost_usd: float
    model_cost_batch_usd: float

    @property
    def per_company_usd(self) -> float:
        return round(self.model_cost_usd / self.companies, 4) if self.companies else 0.0


def estimate_run(n_companies: int) -> RunEstimate:
    extract = (EXTRACT_IN_TOK * SONNET_IN + EXTRACT_OUT_TOK * SONNET_OUT) / 1e6
    score = (SCORE_IN_TOK * OPUS_IN + SCORE_OUT_TOK * OPUS_OUT) / 1e6
    per_company = extract + score
    total = round(per_company * n_companies, 2)
    return RunEstimate(
        companies=n_companies,
        serp_searches=n_companies * SERP_SEARCHES_PER_COMPANY,
        exa_requests=n_companies * EXA_REQUESTS_PER_COMPANY,
        pplx_requests=n_companies * PPLX_REQUESTS_PER_COMPANY,
        model_cost_usd=total,
        model_cost_batch_usd=round(total * BATCH_DISCOUNT, 2),
    )


def serp_quota_check(est: RunEstimate) -> str | None:
    """Compare the run's SERP need against the LIVE remaining SerpAPI quota.

    Uses the free /account endpoint (no search consumed). Returns a verdict
    line, or None when no key is configured.
    """
    try:
        from app.tools.usage import serpapi_panel
    except Exception:
        return None
    panel = serpapi_panel()
    if not panel["configured"] or not panel["ok"]:
        return None
    remaining = panel.get("remaining")
    if remaining is None:
        return None
    if est.serp_searches <= remaining:
        return (f"SerpAPI quota OK: run needs {est.serp_searches} searches, "
                f"{remaining} remaining this month ({panel.get('plan')}).")
    # Read the Serper key the SAME way the engine will at run time — via
    # EngineConfig.load(), which loads .env into the environment first. Reading
    # os.environ directly here gave a false "no backup" during --estimate (the
    # estimate path runs before the engine loads .env).
    try:
        from pipeline.config import EngineConfig
        has_serper = bool(EngineConfig.load().serper_api_key)
    except Exception:
        import os
        has_serper = bool(os.environ.get("SERPER_API_KEY"))
    if has_serper:
        # Not a blocker: the SERP layer drains SerpAPI then falls back to Serper.
        # (Deliberately no "INSUFFICIENT" — the run guardrail keys off that word.)
        return (f"SerpAPI has {remaining} searches left; the run needs "
                f"{est.serp_searches}. That's fine — SerpAPI is drained first, then "
                f"the run falls back to the Serper backup automatically (no crash).")
    return (f"⚠ SerpAPI quota INSUFFICIENT: run needs {est.serp_searches} searches "
            f"but only {remaining} remain this month, and no Serper backup is "
            f"configured — add SERPER_API_KEY, shrink the run (--top), or wait for "
            f"the monthly reset.")


def render(est: RunEstimate, quota_line: str | None = None,
          social_scan: bool = False) -> str:
    lines = [
        "═══ PRE-FLIGHT ESTIMATE (nothing has been spent) ═══",
        f"Companies:            {est.companies}",
        f"SerpAPI searches:     {est.serp_searches}  (News + Jobs + EU registry)",
        f"Exa requests:         {est.exa_requests}  (Q1/Q2/Q3)",
        f"Perplexity requests:  {est.pplx_requests}  (Sonar)",
        f"Model bill (list):    ${est.model_cost_usd}  (~${est.per_company_usd}/company)",
        f"Model bill (Batch):   ${est.model_cost_batch_usd}  (-50% — milestone M7)",
    ]
    if quota_line:
        lines.append(quota_line)
    if social_scan:
        lines.append(
            "Social scan (--social-scan): ON — $0 API cost (Twitter/Reddit/LinkedIn "
            "jobs/Instagram/YouTube via agent-reach's CLIs), but browser-automation-"
            "slow and rate-limited by each platform. Sized for a shortlist, not the "
            f"full universe — {est.companies} companies × 5 platforms will be slow."
        )
    lines.append("Run for real by replacing --estimate with --live.")
    return "\n".join(lines)
