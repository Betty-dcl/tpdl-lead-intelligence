"""Brand memory API — view and update TPDL editorial memory."""
import logging
from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel

from app.tools.memory import (
    get_memory, update_brand_voice, record_feedback, get_brand_voice_block
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/memory", tags=["memory"])


class BrandVoicePatch(BaseModel):
    tone:      Optional[str] = None
    audience:  Optional[str] = None
    avoid:     Optional[list[str]] = None
    structure: Optional[str] = None
    examples:  Optional[list[str]] = None


class FeedbackRequest(BaseModel):
    subject:         str
    format_id:       str
    decision:        str   # "approved" | "rejected"
    content_preview: Optional[str] = None


@router.get("")
def get_full_memory() -> dict:
    return get_memory()


@router.get("/brand-voice-block")
def brand_voice_block() -> dict:
    return {"block": get_brand_voice_block()}


@router.patch("/brand-voice")
def patch_brand_voice(patch: BrandVoicePatch) -> dict:
    updates = {k: v for k, v in patch.model_dump().items() if v is not None}
    if not updates:
        return get_memory().get("brand_voice", {})
    return update_brand_voice(updates)


@router.post("/feedback")
def add_feedback(req: FeedbackRequest) -> dict:
    record_feedback(
        subject=req.subject,
        format_id=req.format_id,
        decision=req.decision,
        content_preview=req.content_preview or "",
    )
    return {"status": "recorded"}
