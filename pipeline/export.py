"""Step 6 — Output: CompanyResult → scored_results.csv (38 columns).

The header matches data/csv/scored_results.csv and import_csv.py EXACTLY,
so every engine run re-imports into the dashboard with zero glue:

    python -m pipeline.runner --company "X" --out data/csv/engine_run.csv
    python import_csv.py data/csv/engine_run.csv
"""
from __future__ import annotations

import csv
from pathlib import Path

from pipeline.config import EngineConfig
from pipeline.types import CompanyResult, ScoredSignal

# The exact 38-column contract (order matters — mirrors the reference CSV).
CSV_HEADERS = [
    "Company Name", "Sector", "Website", "Location", "Revenue",
    "Assessed Score", "Coverage", "Outreach Eligible",
    "Intelligence Summary", "Signals Found", "Signals Not Evidenced",
    "Signal 1 Category", "Signal 1 What Happened", "Signal 1 Why It Matters",
    "Signal 1 TPDL Relevance", "Signal 1 Confidence", "Signal 1 Sources", "Signal 1 URLs",
    "Signal 2 Category", "Signal 2 What Happened", "Signal 2 Why It Matters",
    "Signal 2 TPDL Relevance", "Signal 2 Confidence", "Signal 2 Sources", "Signal 2 URLs",
    "Signal 3 Category", "Signal 3 What Happened", "Signal 3 Why It Matters",
    "Signal 3 TPDL Relevance", "Signal 3 Confidence", "Signal 3 Sources", "Signal 3 URLs",
    "Tech Stack Summary", "Historical Context Summary",
    "ICP Flag", "Review Flag", "Review Flag Reason", "Run Date",
]


def _signal_cells(s: ScoredSignal | None) -> dict[str, str]:
    if s is None:
        return {"Category": "", "What Happened": "", "Why It Matters": "",
                "TPDL Relevance": "", "Confidence": "", "Sources": "", "URLs": ""}
    return {
        "Category": s.signal.category,
        "What Happened": s.signal.what_happened,
        "Why It Matters": s.signal.why_it_matters,
        "TPDL Relevance": s.signal.tpdl_relevance or "",
        "Confidence": s.signal.confidence,
        "Sources": "; ".join(sorted({e.source for e in s.signal.evidence})),
        "URLs": "; ".join(sorted({e.url for e in s.signal.evidence if e.url})),
    }


def result_row(result: CompanyResult, cfg: EngineConfig) -> dict[str, str]:
    top = result.top3()
    row: dict[str, str] = {
        "Company Name": result.name,
        "Sector": result.sector or "",
        "Website": result.website or "",
        "Location": result.location or "",
        "Revenue": result.revenue or "",
        "Assessed Score": f"{result.assessed_score:.1f}",
        "Coverage": result.coverage,
        "Outreach Eligible": "TRUE" if result.outreach_eligible(cfg.outreach_threshold) else "FALSE",
        "Intelligence Summary": result.intelligence_summary,
        "Signals Found": str(len(result.signals)),
        "Signals Not Evidenced": "; ".join(result.signals_not_evidenced),
        "Tech Stack Summary": result.tech_stack_summary or "",
        "Historical Context Summary": result.historical_context or "",
        "ICP Flag": "TRUE" if result.icp_flag else "FALSE",
        "Review Flag": "TRUE" if result.review_flag else "FALSE",
        "Review Flag Reason": result.review_flag_reason or "",
        "Run Date": result.run_date,
    }
    for slot in (1, 2, 3):
        s = top[slot - 1] if len(top) >= slot else None
        for suffix, value in _signal_cells(s).items():
            row[f"Signal {slot} {suffix}"] = value
    return row


def write_csv(results: list[CompanyResult], cfg: EngineConfig, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        for r in results:
            writer.writerow(result_row(r, cfg))
    return path
