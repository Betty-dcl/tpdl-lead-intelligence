"""Content pipeline — Iris finds subjects, Marc writes, Oliver formats.

POST /api/pipeline/run   → full pipeline run (subject optional)
GET  /api/pipeline/runs  → history of runs
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import AgentID, settings
from app.database import get_db
from app.models import ActivityLog, Agent, Task

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])

PIPELINE_FORMATS = ["linkedin", "pdf_a4"]  # default formats for auto-pipeline


class PipelineRunRequest(BaseModel):
    subject:     Optional[str] = None   # if None, Iris picks the top subject
    formats:     list[str] = PIPELINE_FORMATS
    web_search:  bool = True


async def _call_claude_one_shot(agent_record: Agent, prompt: str, max_tokens: int = 1024) -> str:
    from app.agents.base import get_async_anthropic_client
    client = get_async_anthropic_client()
    response = await client.messages.create(
        model=settings.anthropic_model,
        system=agent_record.system_prompt,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
    )
    return "".join(
        b.text for b in response.content if getattr(b, "type", "") == "text"
    )


@router.post("/run")
async def run_pipeline(req: PipelineRunRequest, db: Session = Depends(get_db)) -> dict:
    """Full pipeline: Iris → Marc (all formats) → return results.

    Async: web searches run in worker threads, Marc generates every format
    in parallel. The server stays responsive for the rest of the team.
    """
    import asyncio

    if not settings.anthropic_api_key or settings.anthropic_api_key == "not-set":
        raise HTTPException(status_code=502, detail="ANTHROPIC_API_KEY is not set.")

    iris = db.get(Agent, AgentID.IRIS.value)
    marc = db.get(Agent, AgentID.MARC.value)
    if not iris or not marc:
        raise HTTPException(status_code=404, detail="Agents not found — run `make seed`.")

    # ── Step 1: Iris — find or validate subject ─────────────────────────────
    iris_output = ""
    subject = req.subject

    if not subject:
        try:
            from app.tools.web_search import build_search_context
            from app.tools.memory import get_memory
            mem = get_memory()
            treated = mem.get("treated_subjects", [])
            treated_str = ", ".join(treated[-10:]) if treated else "none yet"

            search_raw = await asyncio.to_thread(
                build_search_context,
                subject="pharma life sciences digital innovation trends",
                sector_hint="pharma medtech dental",
            )
            iris_prompt = (
                f"You are Iris. Based on the search results below, identify the TOP 3 most "
                f"compelling subjects for TPDL content this week. For each subject, give: "
                f"the subject (1 line), why it's relevant NOW (1 sentence), suggested format "
                f"(LinkedIn / PDF A4 / both).\n\n"
                f"Already covered recently (avoid): {treated_str}\n\n"
                f"SEARCH RESULTS:\n{search_raw[:3000]}\n\n"
                f"Output format:\n"
                f"1. SUBJECT: ...\n   WHY NOW: ...\n   FORMAT: ...\n"
                f"2. SUBJECT: ...\n   WHY NOW: ...\n   FORMAT: ...\n"
                f"3. SUBJECT: ...\n   WHY NOW: ...\n   FORMAT: ..."
            )
            iris_output = await _call_claude_one_shot(iris, iris_prompt, max_tokens=512)

            # Extract first subject from Iris output
            for line in iris_output.splitlines():
                if line.strip().upper().startswith("1.") or line.strip().startswith("SUBJECT:"):
                    candidate = line.split(":", 1)[-1].strip().lstrip("1. ")
                    if len(candidate) > 5:
                        subject = candidate[:120]
                        break
        except Exception as exc:
            logger.warning("[pipeline] Iris step failed: %s", exc)

        if not subject:
            subject = "AI transformation in European life sciences"

    logger.info("[pipeline] subject: %s", subject)

    # ── Step 2: Marc — generate all requested formats IN PARALLEL ───────────
    from app.routers.marketing import FORMAT_PROMPTS, FORMAT_LABELS, VALID_FORMATS
    from app.tools.memory import get_brand_voice_block, record_subject

    memory_block = "\n\n" + get_brand_voice_block()
    search_context = ""
    if req.web_search:
        try:
            from app.tools.web_search import build_search_context
            search_context = await asyncio.to_thread(
                build_search_context, subject=subject, sector_hint="pharma life sciences",
            )
        except Exception as exc:
            logger.warning("[pipeline] web search failed: %s", exc)

    formats = [f for f in req.formats if f in VALID_FORMATS]

    async def _generate(fmt: str) -> tuple[str, dict]:
        try:
            prompt = (
                FORMAT_PROMPTS[fmt].format(
                    subject=subject,
                    context="TPDL audience: VP and C-suite in pharma, medtech, dental. European focus.",
                )
                + (f"\n\n{search_context}" if search_context else "")
                + memory_block
            )
            content = await _call_claude_one_shot(marc, prompt, max_tokens=2048)
            result = {"label": FORMAT_LABELS[fmt], "content": content}
            # Reviewer pass — same scoring as the Carousel Studio
            if content:
                from app.tools.content_score import score_content
                result["review"] = await score_content(
                    content=content, format_label=FORMAT_LABELS[fmt], subject=subject,
                )
            return fmt, result
        except Exception as exc:
            logger.error("[pipeline] Marc failed for %s: %s", fmt, exc)
            return fmt, {"label": FORMAT_LABELS[fmt], "content": None, "error": str(exc)}

    pairs = await asyncio.gather(*[_generate(fmt) for fmt in formats])
    marc_results: dict[str, dict] = dict(pairs)

    # ── Persist as a Task ────────────────────────────────────────────────────
    try:
        record_subject(subject, formats)
        db.add(Task(
            agent_id=AgentID.MARC.value,
            title=f"[Pipeline] {subject[:80]}",
            description=json.dumps({"formats": formats, "iris_subject": bool(not req.subject)}),
            status="done",
            output=json.dumps(marc_results),
        ))
        db.add(ActivityLog(
            agent_id=AgentID.IRIS.value,
            action="pipeline_run",
            activity_metadata=json.dumps({"subject": subject, "formats": formats}),
        ))
        db.commit()
    except Exception as exc:
        logger.warning("[pipeline] persistence failed: %s", exc)

    return {
        "subject":        subject,
        "formats":        formats,
        "iris_output":    iris_output or None,
        "results":        marc_results,
        "search_enriched": bool(search_context),
        "auto_subject":   not bool(req.subject),
        "ran_at":         datetime.now(timezone.utc).isoformat(),
    }


@router.get("/runs")
def list_runs(limit: int = 10, db: Session = Depends(get_db)) -> list[dict]:
    """Return last N pipeline runs (tasks created by pipeline)."""
    rows = (
        db.query(Task)
        .filter(Task.agent_id == AgentID.MARC.value, Task.title.like("[Pipeline]%"))
        .order_by(Task.id.desc())
        .limit(limit)
        .all()
    )
    result = []
    for r in rows:
        try:
            desc = json.loads(r.description or "{}")
            out  = json.loads(r.output or "{}")
        except Exception:
            desc, out = {}, {}
        result.append({
            "id":       r.id,
            "subject":  r.title.removeprefix("[Pipeline] "),
            "formats":  desc.get("formats", []),
            "status":   r.status,
            "results":  out,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return result
