"""Print a ';'-joined list of the companies that are in FRIDAY's discovery list
but NOT in the big run's list — i.e. the ones the big run did not re-surface, so
they still need scoring (Betty 2026-07-23: validate all of Friday, no doubles).

Usage:  python scripts/_friday_only_names.py FRIDAY.csv BIGRUN.csv

Standalone (no project import) so it runs by path from any cwd. `_norm` mirrors
pipeline.discovery._norm so the match is the engine's."""
import csv
import re
import sys


def _norm(name: str) -> str:
    n = re.sub(r"\(.*?\)", "", name.lower())
    n = re.sub(r"\b(group|holding|ag|sa|sl|gmbh|inc|ltd|llc|europe|international)\b", "", n)
    return re.sub(r"\W+", " ", n).strip()


def _load(path: str) -> dict:
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


friday, big = _load(sys.argv[1]), _load(sys.argv[2])
only_friday = [name for k, name in friday.items() if k not in big]
print(";".join(only_friday))
