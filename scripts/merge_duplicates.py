"""One-off: merge 3 duplicate company name-variants into a single canonical row.

Betty 2026-07-24: a company must appear only ONCE in Sales, but recurrence must
stay visible. The kept row already covers every run date of its duplicate, so
Recurring stays correct (e.g. Sesderma stays 2×, no longer split into two 1× rows).

Pairs (KEEP ← DROP):
  Glenmark Pharmaceuticals            ← Glenmark Pharmaceuticals Europe
  Julphar (Gulf Pharmaceutical Ind.)  ← Julphar
  Sesderma (Mediderma Group)          ← Sesderma

Backs up every affected row to data/duplicates_backup_<stamp>.json BEFORE writing.
Contacts/comments are reassigned to the kept name (people/notes are worth keeping);
the duplicate's own scored rows (signals, run_snapshots, company row, status) are
dropped because the kept row is the canonical, better-scored version.
"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import sys

DB = "data/app.db"
PAIRS = [
    ("Glenmark Pharmaceuticals", "Glenmark Pharmaceuticals Europe"),
    ("Julphar (Gulf Pharmaceutical Industries)", "Julphar"),
    ("Sesderma (Mediderma Group)", "Sesderma"),
]


def _dump(cur, name: str) -> dict:
    out = {}
    for t, col in [("companies", "name"), ("signals", "company_name"),
                   ("run_snapshots", "company_name"), ("contacts", "company_name"),
                   ("comments", "company_name"), ("company_status", "company_name")]:
        try:
            cur.execute(f"SELECT * FROM {t} WHERE {col}=?", (name,))
            cols = [d[0] for d in cur.description]
            out[t] = [dict(zip(cols, r)) for r in cur.fetchall()]
        except sqlite3.OperationalError:
            out[t] = []
    return out


def _reassign(cur, table: str, keep: str, drop: str) -> None:
    """Move rows (people/notes) from drop → keep; on a PK/unique clash, drop them."""
    try:
        cur.execute(f"UPDATE {table} SET company_name=? WHERE company_name=?", (keep, drop))
    except sqlite3.IntegrityError:
        cur.execute(f"DELETE FROM {table} WHERE company_name=?", (drop,))


def main() -> None:
    dry = "--dry-run" in sys.argv
    con = sqlite3.connect(DB)
    cur = con.cursor()

    backup = {}
    for keep, drop in PAIRS:
        backup[keep] = _dump(cur, keep)
        backup[drop] = _dump(cur, drop)

    stamp = "2026-07-24"
    bpath = pathlib.Path(f"data/duplicates_backup_{stamp}.json")
    bpath.write_text(json.dumps(backup, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Backup written → {bpath}")

    if dry:
        for keep, drop in PAIRS:
            print(f"  would merge {drop!r} → {keep!r}")
        print("Dry-run — no changes written.")
        con.close()
        return

    for keep, drop in PAIRS:
        # people & notes: keep them, attach to the canonical company
        _reassign(cur, "contacts", keep, drop)
        _reassign(cur, "comments", keep, drop)
        # duplicate's own scored/aggregate rows: the kept row is canonical → drop
        for t in ("signals", "run_snapshots", "company_status"):
            try:
                cur.execute(f"DELETE FROM {t} WHERE company_name=?", (drop,))
            except sqlite3.OperationalError:
                pass
        cur.execute("DELETE FROM companies WHERE name=?", (drop,))
        print(f"  merged {drop!r} → {keep!r}")

    con.commit()
    total = cur.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    print(f"\nDone. companies now: {total}")
    con.close()


if __name__ == "__main__":
    main()
