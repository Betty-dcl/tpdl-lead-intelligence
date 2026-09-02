"""Import the TPDL scored_results.csv into the `companies` table.

Idempotent: re-running updates existing rows in place (by Company Name).
Each row gets an `import_run_id` so we can later compare runs month-over-month.

Usage:
    python import_csv.py [path/to/scored_results.csv]

Default path: data/csv/scored_results.csv
"""
import argparse
import csv
import hashlib
import logging
import sys
from datetime import datetime
from pathlib import Path

from app.database import SessionLocal, init_db
from app.models import Company

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sector bucketing
# ---------------------------------------------------------------------------
#
# The CSV has 138 rows tagged "Unknown" + ~100 long-tail labels with 1 entry
# each ("Medtech / Digital Pathology", "Pharma / B2B Dossier Development"…).
# These destroy any chart or filter. We bucket them into 7 clean groups:
#
#   Pharma · Medtech · Diagnostics · Dermatology · Dental ·
#   Healthcare / Services · Other / Unknown
#
# Rule: case-insensitive substring match, first-match wins, ordered by
# specificity (most specific first).

SECTOR_BUCKETS: list[tuple[str, list[str]]] = [
    # (bucket, list of substrings to match in raw sector label)
    ("Dental", ["dental"]),
    ("Dermatology", ["dermatolog", "dermocos", "aesthetic", "skincare"]),
    ("Diagnostics", ["diagnost", "in vitro", "ivd", "laboratory", "lab services"]),
    ("Medtech", ["medtech", "medical device", "medical equipment", "medical product",
                 "medical imaging", "ophthalmolog", "contact lens", "neurotech",
                 "radiation", "histology", "pathology", "robotics", "implant"]),
    ("Pharma", ["pharma", "biopharm", "biotech", "biolog", "specialty pharma",
                "cdmo", "contract development", "drug discovery", "gene", "cell therap",
                "vaccine", "nutraceut", "veterinary pharma", "radiopharm"]),
    ("Healthcare / Services", ["healthcare", "hospital", "clinic", "academic",
                                "consulting", "cro", "contract research",
                                "rehabilitation", "fertility", "urgent care",
                                "remote diagnostic", "teleradiolog", "health technology",
                                "health it", "health science", "drug knowledge",
                                "regulatory consulting"]),
    ("Other", ["life sciences", "agriculture", "aquaculture", "asset management",
               "financial services", "semiconductor", "aerospace", "professional services",
               "scientific distribution", "infrastructure", "blood analysis"]),
]


def bucket_for(raw_sector: str | None) -> str:
    if not raw_sector or raw_sector.strip().lower() in ("", "unknown", "n/a"):
        return "Unknown"
    low = raw_sector.lower()
    for bucket, needles in SECTOR_BUCKETS:
        for n in needles:
            if n in low:
                return bucket
    return "Other"


# ---------------------------------------------------------------------------
# CSV parsing helpers
# ---------------------------------------------------------------------------

def parse_bool(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().upper() in ("TRUE", "1", "YES", "Y")


def parse_float(value: str | None, default: float = 0.0) -> float:
    if value is None or value.strip() == "":
        return default
    try:
        return float(value.strip())
    except ValueError:
        return default


def parse_int(value: str | None, default: int = 0) -> int:
    if value is None or value.strip() == "":
        return default
    try:
        # Accept "2" or "2 of 6 signal types evidenced"
        return int(value.strip().split()[0])
    except (ValueError, IndexError):
        return default


def parse_datetime(value: str | None) -> datetime | None:
    if not value or not value.strip():
        return None
    s = value.strip()
    # Try ISO formats; CSV has e.g. "2026-05-25T16:31:04.121370+00:00"
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            d = datetime.strptime(s, fmt)
            # Strip tz for SQLite (column is naive)
            if d.tzinfo is not None:
                d = d.replace(tzinfo=None)
            return d
        except ValueError:
            continue
    logger.warning("Could not parse date: %r", value)
    return None


def empty_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    s = value.strip()
    return s if s else None


# ---------------------------------------------------------------------------
# Main import
# ---------------------------------------------------------------------------

def import_csv(path: Path) -> None:
    if not path.exists():
        sys.exit(f"CSV not found: {path}")

    init_db()
    # Content-derived run id: re-importing the SAME file is idempotent (same id →
    # its snapshot already exists → skipped below), so Maya's /recurring never
    # counts one dataset imported twice as a fabricated recurrence. A genuinely
    # new run (different content, incl. a fresh run_date) hashes differently.
    run_id = hashlib.sha1(path.read_bytes()).hexdigest()[:12]
    logger.info("Importing %s (run_id=%s)", path, run_id)

    created = 0
    updated = 0

    with SessionLocal() as db:
        with open(path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = (row.get("Company Name") or "").strip()
                if not name:
                    continue

                raw_sector = empty_to_none(row.get("Sector"))
                data = {
                    "name": name,
                    "sector": raw_sector,
                    "sector_bucket": bucket_for(raw_sector),
                    "website": empty_to_none(row.get("Website")),
                    "location": empty_to_none(row.get("Location")),
                    "revenue": empty_to_none(row.get("Revenue")),
                    "assessed_score": parse_float(row.get("Assessed Score")),
                    "coverage": empty_to_none(row.get("Coverage")),
                    "outreach_eligible": parse_bool(row.get("Outreach Eligible")),
                    "intelligence_summary": empty_to_none(row.get("Intelligence Summary")),
                    "signals_found": parse_int(row.get("Signals Found")),
                    "signals_not_evidenced": empty_to_none(row.get("Signals Not Evidenced")),
                    # Signal 1
                    "s1_category":       empty_to_none(row.get("Signal 1 Category")),
                    "s1_what_happened":  empty_to_none(row.get("Signal 1 What Happened")),
                    "s1_why_it_matters": empty_to_none(row.get("Signal 1 Why It Matters")),
                    "s1_tpdl_relevance": empty_to_none(row.get("Signal 1 TPDL Relevance")),
                    "s1_confidence":     empty_to_none(row.get("Signal 1 Confidence")),
                    "s1_sources":        empty_to_none(row.get("Signal 1 Sources")),
                    "s1_urls":           empty_to_none(row.get("Signal 1 URLs")),
                    # Signal 2
                    "s2_category":       empty_to_none(row.get("Signal 2 Category")),
                    "s2_what_happened":  empty_to_none(row.get("Signal 2 What Happened")),
                    "s2_why_it_matters": empty_to_none(row.get("Signal 2 Why It Matters")),
                    "s2_tpdl_relevance": empty_to_none(row.get("Signal 2 TPDL Relevance")),
                    "s2_confidence":     empty_to_none(row.get("Signal 2 Confidence")),
                    "s2_sources":        empty_to_none(row.get("Signal 2 Sources")),
                    "s2_urls":           empty_to_none(row.get("Signal 2 URLs")),
                    # Signal 3
                    "s3_category":       empty_to_none(row.get("Signal 3 Category")),
                    "s3_what_happened":  empty_to_none(row.get("Signal 3 What Happened")),
                    "s3_why_it_matters": empty_to_none(row.get("Signal 3 Why It Matters")),
                    "s3_tpdl_relevance": empty_to_none(row.get("Signal 3 TPDL Relevance")),
                    "s3_confidence":     empty_to_none(row.get("Signal 3 Confidence")),
                    "s3_sources":        empty_to_none(row.get("Signal 3 Sources")),
                    "s3_urls":           empty_to_none(row.get("Signal 3 URLs")),
                    # Context
                    "tech_stack_summary": empty_to_none(row.get("Tech Stack Summary")),
                    "historical_context": empty_to_none(row.get("Historical Context Summary")),
                    # Flags
                    "icp_flag":           parse_bool(row.get("ICP Flag")),
                    "icp_flag_reason":    empty_to_none(row.get("ICP Flag Reason")),
                    "review_flag":        parse_bool(row.get("Review Flag")),
                    "review_flag_reason": empty_to_none(row.get("Review Flag Reason")),
                    # Run
                    "run_date":      parse_datetime(row.get("Run Date")),
                    "import_run_id": run_id,
                }

                existing = db.get(Company, name)
                if existing is None:
                    db.add(Company(**data))
                    created += 1
                else:
                    for k, v in data.items():
                        if k == "name":
                            continue
                        setattr(existing, k, v)
                    updated += 1

        db.commit()

    logger.info("Imported: %d created, %d updated (run_id=%s)", created, updated, run_id)

    # Quick stats
    with SessionLocal() as db:
        from sqlalchemy import func as sql_func
        total = db.query(sql_func.count(Company.name)).scalar()
        eligible = db.query(sql_func.count(Company.name)).filter(Company.outreach_eligible.is_(True)).scalar()
        icp = db.query(sql_func.count(Company.name)).filter(Company.icp_flag.is_(True)).scalar()
        review = db.query(sql_func.count(Company.name)).filter(Company.review_flag.is_(True)).scalar()
        buckets = (
            db.query(Company.sector_bucket, sql_func.count(Company.name))
            .group_by(Company.sector_bucket)
            .order_by(sql_func.count(Company.name).desc())
            .all()
        )

    logger.info("Total: %d · Outreach eligible: %d · ICP flagged: %d · Review flagged: %d",
                total, eligible, icp, review)
    logger.info("Sector buckets: %s", ", ".join(f"{b}={n}" for b, n in buckets))

    # Rebuild the normalised signals table from the freshly imported columns
    from app.tools.signals_sync import sync_signals_from_companies
    with SessionLocal() as db:
        sync_signals_from_companies(db)

    # Append a per-run score snapshot (append-only history — the `companies`
    # table is overwritten in place, so this is what lets Maya compare runs).
    from sqlalchemy import func as sql_func
    from app.models import RunSnapshot
    with SessionLocal() as db:
        # Idempotent: if this exact run is already in history (same content hash),
        # don't append a duplicate — that would be a phantom 2nd run for /recurring.
        already = (db.query(sql_func.count(RunSnapshot.id))
                   .filter(RunSnapshot.import_run_id == run_id).scalar() or 0)
        if already:
            logger.info("Run %s already in history (%d snapshots) — skipping "
                        "(idempotent re-import).", run_id, already)
        else:
            for c in db.query(Company).filter(Company.import_run_id == run_id).all():
                db.add(RunSnapshot(
                    import_run_id=run_id,
                    company_name=c.name,
                    assessed_score=c.assessed_score,
                    coverage=c.coverage,
                    outreach_eligible=c.outreach_eligible,
                    signals_found=c.signals_found,
                    run_date=c.run_date,
                ))
            db.commit()
        snap_runs = db.query(
            sql_func.count(sql_func.distinct(RunSnapshot.import_run_id))
        ).scalar() or 0
    logger.info("Run snapshot saved (run_id=%s). Distinct runs in history: %d",
                run_id, snap_runs)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", nargs="?", default="data/csv/scored_results.csv",
                        help="Path to scored_results.csv")
    args = parser.parse_args()
    import_csv(Path(args.csv))
