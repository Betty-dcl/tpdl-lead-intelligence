"""Compare two discovery candidate lists (Friday vs the big run) and write a
comparison CSV — WITHOUT merging them (Betty 2026-07-23: keep the runs separate,
see the difference, merge later).

Usage:  python scripts/compare_discoveries.py FRIDAY.csv BIG.csv OUT.csv

Status per company:
  common  — found in BOTH lists (Friday's candidate re-confirmed by the big run)
  new     — only in the BIG run (genuinely new this run)
  dropped — only in FRIDAY (found Friday, not re-surfaced by the big run)

Standalone (no project import) so it runs by path from any cwd. `_norm` mirrors
pipeline.discovery._norm so the match is the engine's (e.g. 'Sesderma' ==
'Sesderma (Mediderma Group)')."""
import csv
import re
import sys


def _norm(name: str) -> str:
    n = re.sub(r"\(.*?\)", "", name.lower())
    n = re.sub(r"\b(group|holding|ag|sa|sl|gmbh|inc|ltd|llc|europe|international)\b", "", n)
    return re.sub(r"\W+", " ", n).strip()


def _load(path: str) -> dict:
    """{normalised_key: display_name} for one discovery CSV (empty if missing)."""
    out: dict[str, str] = {}
    try:
        with open(path, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                name = (r.get("Company Name") or "").strip()
                k = _norm(name)
                if k and k not in out:
                    out[k] = name
    except FileNotFoundError:
        pass
    return out


def main() -> None:
    friday_path, big_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    friday, big = _load(friday_path), _load(big_path)
    keys = sorted(set(friday) | set(big), key=lambda k: (friday.get(k) or big.get(k)).lower())

    counts = {"common": 0, "new": 0, "dropped": 0}
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Company", "In Friday", "In Big Run", "Status"])
        for k in keys:
            in_f, in_b = k in friday, k in big
            status = "common" if (in_f and in_b) else "new" if in_b else "dropped"
            counts[status] += 1
            w.writerow([big.get(k) or friday.get(k),
                        "yes" if in_f else "no",
                        "yes" if in_b else "no", status])

    print(f"Comparison written → {out_path}")
    print(f"  Friday list : {len(friday)}")
    print(f"  Big run     : {len(big)}")
    print(f"  common (in both)          : {counts['common']}")
    print(f"  new (only in the big run) : {counts['new']}")
    print(f"  dropped (only in Friday)  : {counts['dropped']}")


if __name__ == "__main__":
    main()
