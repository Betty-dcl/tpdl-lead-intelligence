"""OneDrive CSV API — refresh the team's shared CSV on demand."""
import logging
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.tools.onedrive_csv import fetch_csv_safe

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/onedrive", tags=["onedrive"])

# The client-supplied override may only point at Microsoft share hosts —
# otherwise the endpoint would let anyone make the server fetch arbitrary
# URLs (SSRF). The configured ONEDRIVE_CSV_URL from .env stays fully trusted.
_ALLOWED_HOST_SUFFIXES = (
    "onedrive.live.com", "1drv.ms", "sharepoint.com", "api.onedrive.com",
)


def _is_allowed_share_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and any(
        host == s or host.endswith("." + s) for s in _ALLOWED_HOST_SUFFIXES
    )


class RefreshRequest(BaseModel):
    url: Optional[str] = None   # override the configured link (for testing)


@router.get("/status")
def status() -> dict:
    return {"configured": bool(settings.onedrive_csv_url)}


@router.post("/refresh")
async def refresh(req: RefreshRequest | None = None) -> dict:
    """Download + parse the shared CSV. Returns rows + columns or an error.

    Async: the download runs in a worker thread so a slow OneDrive response
    never freezes the server for other users."""
    import asyncio

    override = req.url.strip() if req and req.url else None
    if override and not _is_allowed_share_url(override):
        raise HTTPException(
            status_code=422,
            detail="URL override must be an https OneDrive/SharePoint share link.",
        )
    url = override or settings.onedrive_csv_url
    result = await asyncio.to_thread(fetch_csv_safe, url)
    return {
        "ok":       result["ok"],
        "error":    result["error"],
        "columns":  result["columns"],
        "row_count": len(result["rows"]),
        "rows":     result["rows"][:500],   # cap payload
    }
