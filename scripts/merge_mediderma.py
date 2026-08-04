"""One-off: merge the two same-group derma rows into ONE, naming both brands.

Betty 2026-08-03: "fusionne, mais nomme quand même les deux." Mediderma and
Sesderma are the same group (Sesderma S.L., Puçol/Puzol, ES) scored as two rows:
  KEEP  'Mediderma (Sesderma Group)'  8.0  eligible  ← ICP-named target
  DROP  'Sesderma (Mediderma Group)'  7.8  not eligible

We keep the eligible ICP row (its signals + run_snapshots history 6.0→8.0) and
rename it so both brands stay visible: 'Mediderma / Sesderma'. The dropped row's
scored rows are removed (people/notes tables are all empty for both). Reversible:
every affected row is dumped to data/mediderma_backup_<stamp>.json first.

NOTE: data/app.db is gitignored; a future re-score reintroduces separate rows
unless the discovery/ICP layer is taught this alias. Demo-cleanliness patch.
"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import sys

DB = "data/app.db"
STAMP = "2026-08-03"
KEEP = "Mediderma (Sesderma Group)"
DROP = "Sesderma (Mediderma Group)"
NEW = "Mediderma / Sesderma"

# (table, company-name column) — every table that references a company by name.
REFS = [
    ("companies", "name"),
    ("signals", "company_name"),
    ("run_snapshots", "company_name"),
    ("company_status", "company_name"),
    ("company_assignments", "company_name"),
    ("specialist_outputs", "company_name"),
    ("contacts", "company_name"),
    ("comments", "company_name"),
]


def _dump(cur, name: str) -> dict:
    out = {}
    for t, col in REFS:
        try:
            cur.execute(f"SELECT * FROM {t} WHERE {col}=?", (name,))
            cols = [d[0] for d in cur.description]
            out[t] = [dict(zip(cols, r)) for r in cur.fetchall()]
        except sqlite3.OperationalError:
            out[t] = []
    return out


def main() -> None:
    dry = "--dry-run" in sys.argv
    con = sqlite3.connect(DB)
    cur = con.cursor()

    backup = {KEEP: _dump(cur, KEEP), DROP: _dump(cur, DROP)}
    bpath = pathlib.Path(f"data/mediderma_backup_{STAMP}.json")
    bpath.write_text(json.dumps(backup, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Backup written → {bpath}\n")

    print(f"  DROP {DROP!r} (all scored rows removed)")
    print(f"  KEEP {KEEP!r} → rename to {NEW!r}")

    if dry:
        print("\nDry-run — no changes written.")
        con.close()
        return

    # 1. remove the dropped row everywhere
    for t, col in REFS:
        try:
            cur.execute(f"DELETE FROM {t} WHERE {col}=?", (DROP,))
        except sqlite3.OperationalError:
            pass

    # 2. rename the kept row everywhere (guard against a name clash)
    for t, col in REFS:
        try:
            cur.execute(f"UPDATE {t} SET {col}=? WHERE {col}=?", (NEW, KEEP))
        except sqlite3.IntegrityError:
            cur.execute(f"DELETE FROM {t} WHERE {col}=?", (KEEP,))
        except sqlite3.OperationalError:
            pass

    con.commit()
    total = cur.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    row = cur.execute(
        "SELECT name, assessed_score, outreach_eligible FROM companies WHERE name=?",
        (NEW,)).fetchone()
    print(f"\nDone. companies now: {total}. Merged row: {row}")
    con.close()


if __name__ == "__main__":
    main()
