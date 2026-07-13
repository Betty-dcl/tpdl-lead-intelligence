"""Rebuild the normalised `signals` table from the Company staging columns.

The CSV import writes signals into Company.s1_/s2_/s3_ columns (1:1 with the
CSV). This sync explodes them into one row per signal so queries can filter
and aggregate cleanly. Idempotent: wipe & rebuild (fast for <10k companies).

Called from app startup (lifespan) and at the end of import_csv.py.
"""
import logging

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def sync_signals_from_companies(db: Session) -> int:
    from app.models import Company, Signal

    db.query(Signal).delete()

    count = 0
    for c in db.query(Company).all():
        for i in (1, 2, 3):
            category = getattr(c, f"s{i}_category")
            if not category:
                continue
            db.add(Signal(
                company_name=c.name,
                slot=i,
                category=category,
                what_happened=getattr(c, f"s{i}_what_happened"),
                why_it_matters=getattr(c, f"s{i}_why_it_matters"),
                tpdl_relevance=getattr(c, f"s{i}_tpdl_relevance"),
                confidence=getattr(c, f"s{i}_confidence"),
                sources=getattr(c, f"s{i}_sources"),
                urls=getattr(c, f"s{i}_urls"),
            ))
            count += 1

    db.commit()
    logger.info("[signals_sync] rebuilt %d signal rows", count)
    return count
