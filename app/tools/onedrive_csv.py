"""OneDrive shared CSV reader.

Lets the deployed platform pull a CSV the team maintains in OneDrive, on demand
(via a "Refresh" button). Read-only: we never write back to OneDrive.

How it works:
  • The team shares the CSV in OneDrive → "Copy link" (anyone with the link can VIEW).
  • We convert that share link into a DIRECT-DOWNLOAD URL.
  • On refresh, the server downloads + parses the CSV into rows.

Set the link via env var ONEDRIVE_CSV_URL (or pass explicitly).
No Microsoft auth needed — the share link is self-contained.
"""
import base64
import csv
import io
import logging
from typing import Optional

import urllib.request

logger = logging.getLogger(__name__)


def to_direct_download(share_url: str) -> str:
    """Convert a OneDrive/SharePoint share link into a direct-download URL.

    OneDrive personal share links can be turned into direct downloads by
    base64-encoding the URL and using the /shares/ Graph-style redirect.
    Works for '1drv.ms' and 'onedrive.live.com' links.
    """
    share_url = share_url.strip()

    # Already a direct download? leave it.
    if "download=1" in share_url or share_url.endswith(".csv"):
        return share_url

    # OneDrive for Business / SharePoint: append ?download=1
    if "sharepoint.com" in share_url or "-my.sharepoint" in share_url:
        sep = "&" if "?" in share_url else "?"
        return f"{share_url}{sep}download=1"

    # OneDrive personal: base64 encode → https://api.onedrive.com/v1.0/shares/<token>/root/content
    b64 = base64.urlsafe_b64encode(share_url.encode("utf-8")).decode("utf-8").rstrip("=")
    token = "u!" + b64
    return f"https://api.onedrive.com/v1.0/shares/{token}/root/content"


def fetch_csv_rows(share_url: str, timeout: int = 20) -> list[dict]:
    """Download the shared CSV and return a list of row dicts (header-keyed)."""
    direct = to_direct_download(share_url)
    logger.info("[onedrive] fetching CSV (direct=%s)", direct[:80])

    req = urllib.request.Request(direct, headers={"User-Agent": "TPDL-AI-Team/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()

    # Decode (handle BOM + common encodings)
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError("Could not decode CSV (unknown encoding).")

    # Sniff delimiter (Excel FR often uses ';')
    sample = text[:2048]
    delimiter = ";" if sample.count(";") > sample.count(",") else ","

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    rows = [dict(r) for r in reader]
    logger.info("[onedrive] parsed %d rows, %d columns", len(rows),
                len(rows[0]) if rows else 0)
    return rows


def fetch_csv_safe(share_url: Optional[str]) -> dict:
    """Wrapper that never raises — returns {ok, rows, columns, error}."""
    if not share_url:
        return {"ok": False, "rows": [], "columns": [], "error": "No OneDrive CSV link configured."}
    try:
        rows = fetch_csv_rows(share_url)
        columns = list(rows[0].keys()) if rows else []
        return {"ok": True, "rows": rows, "columns": columns, "error": None}
    except Exception as exc:
        logger.warning("[onedrive] fetch failed: %s", exc)
        return {"ok": False, "rows": [], "columns": [], "error": str(exc)}
