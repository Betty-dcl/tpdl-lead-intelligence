"""Fill missing sector / revenue / website for a run's companies — ONE Perplexity
call per company (cheap), fail-open (never fabricates: unknown → left blank).

Usage:
    python scripts/enrich_run.py [--run YYYY-MM-DD] [--limit N] [--sample N]

Defaults to the latest run date. Writes straight to the `companies` table; only
overwrites a field when we actually got a value (never blanks existing data).
Runs in-session (Perplexity via urllib, unlike the blocking Anthropic SDK).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sqlite3

from pipeline.config import EngineConfig
from pipeline.enrich import parse_revenue
from import_csv import bucket_for

DB = "data/app.db"
_DOMAIN = re.compile(r"(?:https?://)?(?:www\.)?([a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]+)+)", re.I)


def _line(text: str, key: str) -> str | None:
    """Value after 'KEY:' in the model's 3-line answer, or None if unknown/empty."""
    for ln in (text or "").splitlines():
        s = ln.strip()
        if s.lower().startswith(key.lower() + ":"):
            v = s.split(":", 1)[1].strip().strip("*").strip()
            if not v or any(b in v.lower() for b in ("unknown", "not public", "n/a", "no data")):
                return None
            return v
    return None


def parse_website(text: str | None) -> str | None:
    """Bare registrable domain from the WEBSITE line (e.g. 'example.com')."""
    v = _line(text or "", "WEBSITE")
    if not v:
        return None
    m = _DOMAIN.search(v)
    if not m:
        return None
    dom = m.group(1).lower().rstrip(".")
    # reject obvious non-domains / sentences
    if " " in dom or len(dom) > 63 or dom.count(".") > 3:
        return None
    return dom


def enrich_one(cfg: EngineConfig, name: str, location: str | None) -> dict:
    """One Perplexity call → {sector, revenue, website} (each may be None)."""
    from pipeline.research import _post_json
    from pipeline.usage_log import log_search_calls
    loc = f" (headquartered in {location})" if location else ""
    prompt = (
        f'For the company "{name}"{loc}, reply with EXACTLY three lines, nothing else:\n'
        'SECTOR: a 1-3 word industry (e.g. "Specialty pharma", "Dermatology", '
        '"Diagnostics", "Medical devices", "Dental"); if truly unknown, "unknown".\n'
        'REVENUE: most recent approximate ANNUAL revenue with currency '
        '(e.g. "€250 million", "$1.2 billion"); if not public, "unknown".\n'
        'WEBSITE: the official company homepage URL; if unknown, "unknown".'
    )
    log_search_calls("perplexity", 1, name)
    data = _post_json(
        "https://api.perplexity.ai/chat/completions",
        {"model": "sonar", "messages": [{"role": "user", "content": prompt}]},
        {"Authorization": f"Bearer {cfg.perplexity_api_key}"},
    )
    text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    sector_raw = _line(text, "SECTOR")
    return {
        "sector": sector_raw,
        "sector_bucket": bucket_for(sector_raw) if sector_raw else None,
        "revenue": parse_revenue(text if _line(text, "REVENUE") else None)
                   if _line(text, "REVENUE") else None,
        "website": parse_website(text),
        "_raw": text,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=None, help="run date YYYY-MM-DD (default: latest)")
    ap.add_argument("--limit", type=int, default=0, help="cap number of companies")
    ap.add_argument("--sample", type=int, default=0, help="probe N and print raw answers, no DB write")
    ap.add_argument("--missing-revenue", action="store_true",
                    help="only process companies whose revenue is still blank (cheap re-pass)")
    ap.add_argument("--missing-sector", action="store_true",
                    help="only process companies whose sector is Unknown/blank")
    ap.add_argument("--all-runs", action="store_true",
                    help="ignore --run and process the whole universe")
    args = ap.parse_args()

    cfg = EngineConfig.load(live=True)
    if not cfg.perplexity_api_key:
        sys.exit("No PERPLEXITY_API_KEY in .env — cannot enrich.")

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    run = args.run
    if not run and not args.all_runs:
        run = cur.execute("select max(date(run_date)) from companies").fetchone()[0]

    clauses, params = [], []
    if not args.all_runs:
        clauses.append("date(run_date)=?"); params.append(run)
    if args.missing_revenue:
        clauses.append("(revenue is null or trim(revenue)='')")
    if args.missing_sector:
        clauses.append("(sector_bucket is null or trim(sector_bucket)='' or sector_bucket='Unknown')")
    where = " and ".join(clauses) if clauses else "1=1"
    run = run or "ALL RUNS"
    rows = cur.execute(
        "select name, sector, sector_bucket, website, revenue, location "
        f"from companies where {where} order by assessed_score desc", params
    ).fetchall()
    if args.limit:
        rows = rows[: args.limit]
    if args.sample:
        rows = rows[: args.sample]

    print(f"Run {run}: {len(rows)} companies to process "
          f"({'SAMPLE — no DB write' if args.sample else 'live, writing DB'}).")

    filled = {"sector": 0, "revenue": 0, "website": 0}
    errors = 0
    for i, r in enumerate(rows, 1):
        name = r["name"]
        try:
            res = enrich_one(cfg, name, r["location"])
        except Exception as e:                      # fail-open per company
            errors += 1
            print(f"  [{i}/{len(rows)}] {name}: ERROR {e}")
            continue

        if args.sample:
            print(f"\n── {name} ({r['location']}) ──")
            print(res["_raw"])
            print(f"  → sector={res['sector']!r} bucket={res['sector_bucket']!r} "
                  f"revenue={res['revenue']!r} website={res['website']!r}")
            continue

        sets, params = [], []
        # sector: only when we have one AND current bucket is Unknown/empty
        if res["sector"] and (not r["sector_bucket"] or r["sector_bucket"] == "Unknown"):
            sets += ["sector=?", "sector_bucket=?"]
            params += [res["sector"], res["sector_bucket"]]
            filled["sector"] += 1
        if res["revenue"] and not (r["revenue"] or "").strip():
            sets.append("revenue=?"); params.append(res["revenue"]); filled["revenue"] += 1
        if res["website"] and not (r["website"] or "").strip():
            sets.append("website=?"); params.append(res["website"]); filled["website"] += 1

        if sets:
            params.append(name)
            cur.execute(f"update companies set {', '.join(sets)} where name=?", params)
            con.commit()
        tag = " ".join(f"{k}✓" for k in ("sector", "revenue", "website")
                       if (res[k] and (k != "sector" or res["sector_bucket"])))
        print(f"  [{i}/{len(rows)}] {name}: {tag or '— nothing new'}")

    con.close()
    print(f"\nDone. Filled — sector: {filled['sector']}, revenue: {filled['revenue']}, "
          f"website: {filled['website']} (of {len(rows)}). Errors: {errors}.")


if __name__ == "__main__":
    main()
