"""Backfill the head-office CITY for companies that are missing one.

Why: --enrich-location was silently lost in the batch submit→fetch flow (fixed
in runner.py 2026-07-24), so the 2026-07-23 batch left ~126 companies with no
location. This one-off fills them WITHOUT re-scoring: one Perplexity call per
company (fail-open), updating companies.location in place. Never touches scores.

Usage (from the project root, in the Terminal):
    .venv/bin/python scripts/backfill_hq_city.py            # live, fills all missing
    .venv/bin/python scripts/backfill_hq_city.py --dry-run  # list what WOULD be filled, no spend
    .venv/bin/python scripts/backfill_hq_city.py --limit 20 # cap the number of calls

Cost: ~$0.002/company (Perplexity sonar). Safe to re-run — only touches rows that
still need a city.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

# Runnable by path from any cwd: put the project root on sys.path before the
# app/pipeline imports (running a script by path only adds scripts/ otherwise).
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from app.models import Company
from pipeline import enrich
from pipeline.config import EngineConfig


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="list companies that need a city; make no API call, no write")
    ap.add_argument("--limit", type=int, default=0, help="cap the number processed (0 = all)")
    args = ap.parse_args()

    cfg = EngineConfig.load(live=not args.dry_run)

    with SessionLocal() as db:
        todo = [c for c in db.query(Company).all() if enrich.needs_city(c.location)]
        if args.limit:
            todo = todo[: args.limit]
        print(f"{len(todo)} companies need a city.")
        if args.dry_run:
            for c in todo[:50]:
                print(f"  (would fill) {c.name}  [current: {c.location!r}]")
            print("Dry-run — nothing called, nothing written.")
            return

        filled = 0
        for c in todo:
            city = enrich.estimate_hq_location(cfg, c.name)
            if city:
                c.location = city
                filled += 1
                print(f"  ✓ {c.name} → {city}")
            else:
                print(f"  · {c.name} → (unknown, left as is)")
        db.commit()
        print(f"\nDone: filled {filled}/{len(todo)} cities. Scores untouched.")


if __name__ == "__main__":
    main()
