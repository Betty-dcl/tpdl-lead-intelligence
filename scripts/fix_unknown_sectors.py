"""One-off: classify the last Unknown-sector companies from public knowledge.

Betty 2026-08-03 (data-quality pass): the universe had 5 rows with
sector_bucket='Unknown'. Four are well-known public companies whose industry is
unambiguous — classifying them is categorisation of public fact, NOT signal
fabrication (no dates/events invented). The 5th (Shealed, Brno, score 0) is
obscure and stays Unknown on purpose: we never guess.

Each label is run through import_csv.bucket_for so the bucket matches ingestion
exactly. Backs up affected rows to data/sector_backup_<stamp>.json before writing.

NOTE: data/app.db is gitignored and a future re-score overwrites these fields.
This is a demo-cleanliness patch; the durable fix is enrichment at ingest.
"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from import_csv import bucket_for  # noqa: E402

DB = "data/app.db"
STAMP = "2026-08-03"

# (company name, real public-fact sector label) — Shealed intentionally omitted.
FIXES = [
    ("Slingshot Biosciences", "Diagnostics tools (synthetic cell standards)"),
    ("SYNLAB International", "Medical laboratory diagnostics"),
    ("Henke Sass Wolf", "Medical devices (endoscopy)"),
    ("United Medical Supplies UNIMED L.L.C", "Medical devices distribution"),
]


def main() -> None:
    dry = "--dry-run" in sys.argv
    con = sqlite3.connect(DB)
    cur = con.cursor()

    backup = {}
    plan = []
    for name, label in FIXES:
        cur.execute(
            "SELECT name, sector, sector_bucket FROM companies WHERE name=?", (name,))
        row = cur.fetchone()
        if not row:
            print(f"  ! not found: {name!r} — skipped")
            continue
        backup[name] = {"sector": row[1], "sector_bucket": row[2]}
        bucket = bucket_for(label)
        plan.append((name, label, bucket))

    bpath = pathlib.Path(f"data/sector_backup_{STAMP}.json")
    bpath.write_text(json.dumps(backup, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Backup written → {bpath}\n")

    for name, label, bucket in plan:
        print(f"  {name!r}: Unknown → {bucket}  (sector={label!r})")

    if dry:
        print("\nDry-run — no changes written.")
        con.close()
        return

    for name, label, bucket in plan:
        cur.execute(
            "UPDATE companies SET sector=?, sector_bucket=? WHERE name=?",
            (label, bucket, name))
    con.commit()

    remaining = cur.execute(
        "SELECT COUNT(*) FROM companies WHERE sector_bucket='Unknown'").fetchone()[0]
    print(f"\nDone. Unknown-sector rows now: {remaining} (Shealed kept on purpose).")
    con.close()


if __name__ == "__main__":
    main()
