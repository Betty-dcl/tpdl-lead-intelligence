"""Market Intel mocks aligned with TPDL Lead Intelligence Pipeline.

Pipeline-level stats come straight from PDF Section 2.
Charts are computed from the mock company list (live aggregations) so editing
companies.py automatically reshapes the dashboard.
"""
from datetime import date, timedelta

from app.mocks.companies import MOCK_COMPANIES, SIGNAL_TYPES


# ---- Pipeline-wide stats (PDF Section 2) ------------------------------------

PIPELINE_STATS: dict = {
    "total_companies": 138,
    "after_dedup": 131,
    "icp_flagged": 49,
    "in_scope": 82,
    "domain_missing": 1,
    # Mocked here — would come from the latest run output.
    "outreach_eligible": sum(1 for c in MOCK_COMPANIES if c["outreach_eligible"]),
    "review_flagged": sum(1 for c in MOCK_COMPANIES if c.get("review_flag")),
    "last_run": "2026-05-24T08:00:00",
    "pipeline_version": "v1.0.0",
}


# ---- Sector breakdown (PDF Section 2) ---------------------------------------

SECTOR_TOTALS: list[dict] = [
    {"sector": "Dental",      "total": 54, "in_scope": 32},
    {"sector": "Diagnostics", "total": 44, "in_scope": 22},
    {"sector": "Dermatology", "total": 33, "in_scope": 28},
]


# ---- Chart data: computed from companies ------------------------------------

def score_distribution() -> list[dict]:
    """Buckets of assessed_score for a histogram. 6 buckets, 0–10."""
    buckets = [
        (0.0, 2.0, "0–2"),
        (2.0, 4.0, "2–4"),
        (4.0, 6.0, "4–6"),
        (6.0, 8.0, "6–8"),
        (8.0, 10.0, "8–10"),
    ]
    out = []
    for lo, hi, label in buckets:
        count = sum(1 for c in MOCK_COMPANIES if lo <= c["assessed_score"] < hi)
        out.append({"label": label, "count": count})
    # The top bucket should include 10.0 itself.
    out[-1]["count"] += sum(1 for c in MOCK_COMPANIES if c["assessed_score"] == 10.0)
    return out


def signal_coverage_by_type() -> list[dict]:
    """How many companies have at least one evidenced signal of each type."""
    out = []
    for sig in SIGNAL_TYPES:
        count = sum(1 for c in MOCK_COMPANIES
                    if any(s["category"] == sig for s in c["signals"]))
        out.append({"signal_type": sig, "count": count})
    return out


def tech_stack_gaps() -> dict:
    """% of companies with no CRM detected, % blocked, % with CRM."""
    total = len(MOCK_COMPANIES)
    no_crm = sum(1 for c in MOCK_COMPANIES if c["tech_stack"]["crm"] == "none detected")
    blocked = sum(1 for c in MOCK_COMPANIES if c["tech_stack"]["crm"] == "blocked")
    with_crm = total - no_crm - blocked
    return {
        "total": total,
        "with_crm": with_crm,
        "no_crm_detected": no_crm,
        "scan_blocked": blocked,
    }


def sector_distribution_in_mocks() -> list[dict]:
    """Live count by sector across the mock list — feeds the doughnut chart."""
    counts: dict[str, int] = {}
    for c in MOCK_COMPANIES:
        counts[c["sector"]] = counts.get(c["sector"], 0) + 1
    return [{"sector": k, "count": v} for k, v in sorted(counts.items())]


# ---- Pipeline run timeline (last 6 runs, mocked) ----------------------------

def recent_runs() -> list[dict]:
    today = date.today()
    return [
        {
            "date": (today - timedelta(weeks=i)).isoformat(),
            "companies_scored": 131 - i * 2,
            "outreach_eligible": max(0, 12 - i),
            "review_flagged": 4 + (i % 3),
        }
        for i in range(6)
    ][::-1]
