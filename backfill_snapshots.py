"""Backfill run_snapshots from the current `companies` table (one-time recovery).

Why: RunSnapshot was added AFTER the initial 25/05 import, so the 492 real
companies already in `companies` have no snapshot — `/recurring` sees 0 runs.
This backfills the run that produced the current `companies` rows (identified by
their shared `import_run_id`) into the append-only history, so it counts as a
real run #1. It is NOT a simulation: it recovers a run that genuinely happened.

Idempotent: does nothing for an import_run_id already present in run_snapshots.
From then on, every `python import_csv.py <new.csv>` adds run #2, #3… and
Maya's `/recurring` activates automatically at ≥ 2 runs.

Usage:  python backfill_snapshots.py
"""
import logging

from sqlalchemy import func

from app.database import SessionLocal, init_db
from app.models import Company, RunSnapshot

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] [%(name)s] %(message)s")
logger = logging.getLogger(__name__)


def backfill() -> int:
    """Snapshot each companies-table run absent from run_snapshots. Returns #added."""
    init_db()
    added = 0
    with SessionLocal() as db:
        existing_runs = {
            r[0] for r in db.query(RunSnapshot.import_run_id).distinct().all()
        }
        # Group the current companies by the run that imported them.
        run_ids = [
            r[0] for r in db.query(Company.import_run_id).distinct().all()
            if r[0] and r[0] not in existing_runs
        ]
        if not run_ids:
            logger.info("Nothing to backfill — every companies-table run is "
                        "already in the history (%d distinct runs).",
                        len(existing_runs))
            return 0

        for run_id in run_ids:
            companies = db.query(Company).filter(
                Company.import_run_id == run_id).all()
            for c in companies:
                db.add(RunSnapshot(
                    import_run_id=run_id,
                    company_name=c.name,
                    assessed_score=c.assessed_score,
                    coverage=c.coverage,
                    outreach_eligible=c.outreach_eligible,
                    signals_found=c.signals_found,
                    run_date=c.run_date,
                ))
                added += 1
            logger.info("Backfilled run %s: %d companies", run_id, len(companies))
        db.commit()

        total_runs = db.query(
            func.count(func.distinct(RunSnapshot.import_run_id))).scalar() or 0
    logger.info("Done. Added %d snapshots. Distinct runs in history: %d.",
                added, total_runs)
    if total_runs < 2:
        logger.info("`/recurring` stays blocked until a 2nd real import lands "
                    "(run `python import_csv.py <new_run.csv>`).")
    return added


if __name__ == "__main__":
    backfill()
