"""Print a ';'-joined list of the Company Name column from one discovery CSV.
Standalone (no project import) so it runs by path from any cwd. Helper for
run_big_launch.sh."""
import csv
import sys

seen: set[str] = set()
out: list[str] = []
with open(sys.argv[1], encoding="utf-8") as f:
    for r in csv.DictReader(f):
        name = (r.get("Company Name") or "").strip()
        if name and name.lower() not in seen:
            seen.add(name.lower())
            out.append(name)
print(";".join(out))
