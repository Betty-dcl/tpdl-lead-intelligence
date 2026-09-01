"""One-off, reversible: undo the 2026-08-03 Mediderma/Sesderma merge.

Betty's call (2026-08-31): keep them as TWO separate rows (real brands), but
make sure each name clearly states the shared group — which the pre-merge
names already did ("Mediderma (Sesderma Group)" / "Sesderma (Mediderma
Group)"). Restores the exact pre-merge data from
`data/mediderma_backup_2026-08-03.json` (written by the original merge
script) — nothing invented, nothing re-scored. Deterministic, no network,
no LLM call. Idempotent-ish: safe to re-run (it only ever touches the
"Mediderma / Sesderma" merged row + the two split names).
"""
import json
import logging
from datetime import datetime
from pathlib import Path

from app.database import SessionLocal
from app.models import Company, RunSnapshot
from app.tools.signals_sync import sync_signals_from_companies

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BACKUP = Path(__file__).resolve().parent.parent / "data" / "mediderma_backup_2026-08-03.json"
MERGED_NAME = "Mediderma / Sesderma"


def _parse_dt(s):
    return datetime.fromisoformat(s) if s else None


def main() -> None:
    data = json.loads(BACKUP.read_text())
    with SessionLocal() as db:
        merged = db.get(Company, MERGED_NAME)
        if merged is None:
            logger.warning("No '%s' row found — already split, or never merged. Nothing to do.", MERGED_NAME)
            return

        db.query(RunSnapshot).filter(RunSnapshot.company_name == MERGED_NAME).delete()
        db.delete(merged)
        db.flush()

        for name, blob in data.items():
            row = blob["companies"][0]
            db.merge(Company(
                name=row["name"],
                sector=row["sector"],
                sector_bucket=row["sector_bucket"],
                website=row["website"],
                location=row["location"],
                revenue=row["revenue"],
                assessed_score=row["assessed_score"],
                coverage=row["coverage"],
                outreach_eligible=bool(row["outreach_eligible"]),
                intelligence_summary=row["intelligence_summary"],
                signals_found=row["signals_found"],
                signals_not_evidenced=row["signals_not_evidenced"],
                s1_category=row["s1_category"], s1_what_happened=row["s1_what_happened"],
                s1_why_it_matters=row["s1_why_it_matters"], s1_tpdl_relevance=row["s1_tpdl_relevance"],
                s1_confidence=row["s1_confidence"], s1_sources=row["s1_sources"], s1_urls=row["s1_urls"],
                s2_category=row["s2_category"], s2_what_happened=row["s2_what_happened"],
                s2_why_it_matters=row["s2_why_it_matters"], s2_tpdl_relevance=row["s2_tpdl_relevance"],
                s2_confidence=row["s2_confidence"], s2_sources=row["s2_sources"], s2_urls=row["s2_urls"],
                s3_category=row["s3_category"], s3_what_happened=row["s3_what_happened"],
                s3_why_it_matters=row["s3_why_it_matters"], s3_tpdl_relevance=row["s3_tpdl_relevance"],
                s3_confidence=row["s3_confidence"], s3_sources=row["s3_sources"], s3_urls=row["s3_urls"],
                tech_stack_summary=row["tech_stack_summary"],
                historical_context=row["historical_context"],
                icp_flag=bool(row["icp_flag"]),
                review_flag=bool(row["review_flag"]),
                review_flag_reason=row["review_flag_reason"],
                run_date=_parse_dt(row["run_date"]),
                import_run_id=row["import_run_id"],
                imported_at=_parse_dt(row["imported_at"]),
                review_status=row["review_status"],
                reviewed_at=_parse_dt(row["reviewed_at"]),
                reviewed_note=row["reviewed_note"],
            ))
            for snap in blob["run_snapshots"]:
                db.add(RunSnapshot(
                    import_run_id=snap["import_run_id"],
                    company_name=snap["company_name"],
                    assessed_score=snap["assessed_score"],
                    coverage=snap["coverage"],
                    outreach_eligible=bool(snap["outreach_eligible"]),
                    signals_found=snap["signals_found"],
                    run_date=_parse_dt(snap["run_date"]),
                    imported_at=_parse_dt(snap["imported_at"]),
                ))
            logger.info("restored %s (%d run snapshots)", name, len(blob["run_snapshots"]))

        db.commit()
        n = sync_signals_from_companies(db)
        logger.info("signals table rebuilt: %d rows", n)


if __name__ == "__main__":
    main()
