"""Benchmark harness — measure our engine against the Neotek reference run.

We own Neotek's "exam copy": data/csv/scored_results.csv (492 companies,
run 2026-05-25). Parity with Neotek stops being an opinion and becomes a
measurement: run our engine on the same companies, then compare.

    python -m pipeline.benchmark data/csv/engine_run.csv
    python -m pipeline.benchmark data/csv/engine_run.csv --reference data/csv/scored_results.csv

Zero API calls — pure CSV arithmetic.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass, field
from pathlib import Path

REFERENCE_CSV = Path("data/csv/scored_results.csv")

_SIGNAL_CAT_COLS = ("Signal 1 Category", "Signal 2 Category", "Signal 3 Category")


def _load(path: Path) -> dict[str, dict[str, str]]:
    with open(path, encoding="utf-8", newline="") as f:
        return {row["Company Name"].strip(): row
                for row in csv.DictReader(f) if row.get("Company Name", "").strip()}


def _score(row: dict[str, str]) -> float:
    try:
        return float(row.get("Assessed Score", "") or 0.0)
    except ValueError:
        return 0.0


def _eligible(row: dict[str, str]) -> bool:
    return (row.get("Outreach Eligible", "") or "").strip().upper() == "TRUE"


def _categories(row: dict[str, str]) -> set[str]:
    return {row[c].strip() for c in _SIGNAL_CAT_COLS if row.get(c, "").strip()}


@dataclass
class CompanyDelta:
    name: str
    ref_score: float
    engine_score: float
    eligible_flip: str | None          # "ref-only" | "engine-only" | None
    categories_missed: set[str]        # in reference top-3, absent from ours
    categories_extra: set[str]         # in ours, absent from reference top-3

    @property
    def score_delta(self) -> float:
        return round(self.engine_score - self.ref_score, 1)


@dataclass
class BenchmarkReport:
    compared: list[CompanyDelta] = field(default_factory=list)
    only_in_reference: list[str] = field(default_factory=list)
    only_in_engine: list[str] = field(default_factory=list)

    # ── aggregate metrics ────────────────────────────────────────────────
    @property
    def mae(self) -> float:
        """Mean absolute score error vs reference (lower = closer to Neotek)."""
        if not self.compared:
            return 0.0
        return round(sum(abs(d.score_delta) for d in self.compared) / len(self.compared), 2)

    @property
    def eligibility_agreement(self) -> float:
        """% of companies where outreach eligibility matches the reference."""
        if not self.compared:
            return 0.0
        same = sum(1 for d in self.compared if d.eligible_flip is None)
        return round(100.0 * same / len(self.compared), 1)

    @property
    def category_recall(self) -> float:
        """% of reference top-3 categories our engine also found."""
        ref_total = sum(len(d.categories_missed) + (len(_i(d))) for d in self.compared)
        if ref_total == 0:
            return 100.0
        found = sum(len(_i(d)) for d in self.compared)
        return round(100.0 * found / ref_total, 1)


def _i(d: CompanyDelta) -> set[str]:
    """Reference categories our engine DID find (intersection helper)."""
    return d._intersection  # type: ignore[attr-defined]


def compare(engine_path: Path, reference_path: Path = REFERENCE_CSV) -> BenchmarkReport:
    ref = _load(reference_path)
    eng = _load(engine_path)

    report = BenchmarkReport(
        only_in_reference=sorted(set(ref) - set(eng)),
        only_in_engine=sorted(set(eng) - set(ref)),
    )
    for name in sorted(set(ref) & set(eng)):
        r, e = ref[name], eng[name]
        ref_cats, eng_cats = _categories(r), _categories(e)
        flip = None
        if _eligible(r) and not _eligible(e):
            flip = "ref-only"
        elif _eligible(e) and not _eligible(r):
            flip = "engine-only"
        delta = CompanyDelta(
            name=name,
            ref_score=_score(r),
            engine_score=_score(e),
            eligible_flip=flip,
            categories_missed=ref_cats - eng_cats,
            categories_extra=eng_cats - ref_cats,
        )
        delta._intersection = ref_cats & eng_cats  # type: ignore[attr-defined]
        report.compared.append(delta)
    return report


def render(report: BenchmarkReport, top: int = 15) -> str:
    lines = ["═══ BENCHMARK vs Neotek reference ═══", ""]
    n = len(report.compared)
    lines.append(f"Companies compared: {n}")
    if report.only_in_engine:
        lines.append(f"Only in engine output: {len(report.only_in_engine)} "
                     f"({', '.join(report.only_in_engine[:5])}{'…' if len(report.only_in_engine) > 5 else ''})")
    if report.only_in_reference:
        lines.append(f"Not attempted (in reference only): {len(report.only_in_reference)}")
    if not n:
        lines.append("")
        lines.append("⚠ No overlapping companies — run the engine on companies "
                     "from the reference CSV to measure parity.")
        return "\n".join(lines)

    lines += [
        "",
        f"Score MAE (mean |Δ|):        {report.mae}",
        f"Outreach agreement:          {report.eligibility_agreement}%",
        f"Signal category recall:      {report.category_recall}%",
        "",
        f"── Largest score gaps (top {top}) ──",
    ]
    worst = sorted(report.compared, key=lambda d: abs(d.score_delta), reverse=True)[:top]
    for d in worst:
        flags = []
        if d.eligible_flip:
            flags.append(f"ELIGIBLE FLIP ({d.eligible_flip})")
        if d.categories_missed:
            flags.append(f"missed: {','.join(sorted(d.categories_missed))}")
        if d.categories_extra:
            flags.append(f"extra: {','.join(sorted(d.categories_extra))}")
        lines.append(f"  {d.name:40.40} ref {d.ref_score:>4.1f} → eng {d.engine_score:>4.1f} "
                     f"(Δ {d.score_delta:+.1f})  {' · '.join(flags)}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Engine vs Neotek reference benchmark")
    parser.add_argument("engine_csv", type=Path)
    parser.add_argument("--reference", type=Path, default=REFERENCE_CSV)
    parser.add_argument("--top", type=int, default=15)
    args = parser.parse_args()
    print(render(compare(args.engine_csv, args.reference), top=args.top))


if __name__ == "__main__":
    main()
