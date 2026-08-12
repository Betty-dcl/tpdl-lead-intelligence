import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.mocks import linkedin_drafts, marketing

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/marketing", tags=["marketing"])


# The 7-part editorial doctrine every Marc piece follows (brand-editorial.md §3).
_DOCTRINE_STEPS = (
    "Business Principle", "The Pattern", "The Misdiagnosis",
    "The Principle (TPDL view + root cause)", "Evidence",
    "Executive Implications", "Practical Takeaway",
)
_BANNED_WORDS = (
    "digital transformation", "AI-first", "best-in-class",
    "cutting-edge", "next-generation platform", "omnichannel maturity",
)
# Oliver's formats and whether each renders to a downloadable file.
_OLIVER_FORMATS = (
    {"type": "a4", "label": "A4 article", "file": "PDF"},
    {"type": "ppt", "label": "PowerPoint deck", "file": "PPTX"},
    {"type": "carousel", "label": "LinkedIn carousel", "file": None},
    {"type": "website", "label": "Website article", "file": None},
    {"type": "newsletter", "label": "Email newsletter (70/10/20)", "file": None},
)


@router.get("/pipeline")
def marketing_pipeline(theme: Optional[str] = None, db: Session = Depends(get_db)) -> dict:
    """Live view of the Marketing chain on ONE campaign theme: Iris → Marc → Oliver.

    Deterministic, no LLM call: each stage's real contribution is assembled from
    the shared campaign-theme spine (app/tools/campaign_themes.py). The picker is
    Nathalie's five Market Intel themes; the default is the first. This makes the
    Iris → Marc → Oliver wiring visible the same way /api/intel/pipeline does for
    Sales — each stage consumes the previous stage's output as the agents do."""
    from app.agents.oliver import find_marc_content
    from app.tools.campaign_themes import CAMPAIGN_THEMES, find_theme

    picker = [{"key": t.key, "title": t.title} for t in CAMPAIGN_THEMES]

    target = None
    if theme:
        target = find_theme(theme) or next(
            (t for t in CAMPAIGN_THEMES if t.key == theme.strip().lower()), None)
    if target is None:
        target = CAMPAIGN_THEMES[0]

    marc_content = find_marc_content(db, target.title)

    return {
        "picker": picker,
        "theme": {
            "key": target.key, "title": target.title, "audience": target.audience,
            "business_principle": target.business_principle,
            "angle": target.angle, "reframe": target.reframe,
        },
        # Iris: surfaces the theme, names the business principle it proves, scores
        # it content-worthy for the ICP audience, hands the freshest to Marc.
        "iris": {
            "business_principle": target.business_principle,
            "audience": target.audience,
            "content_worthy": "relevance × timeliness × differentiation — maps to a TPDL business principle",
            "hands_to": "Marc",
        },
        # Marc: grounds the piece in that principle, follows the 7-part doctrine,
        # never starts from a technology, marks unconfirmed numbers.
        "marc": {
            "start_from": target.business_principle,
            "reframe": target.reframe,
            "doctrine": list(_DOCTRINE_STEPS),
            "banned_words": list(_BANNED_WORDS),
            "unverified_marker": "[STAT TO VERIFY]",
        },
        # Oliver: formats Marc's real content (when it exists) for that audience.
        "oliver": {
            "audience": target.audience,
            "formats": list(_OLIVER_FORMATS),
            "marc_content_ready": bool(marc_content),
        },
    }


# ---- Carousel Studio schemas -------------------------------------------------

class CarouselGenerateRequest(BaseModel):
    subject: str
    formats: List[str]          # subset of: linkedin, pdf_a4, website, ppt
    context: Optional[str] = None
    web_search: bool = True     # enrich with live search results
    score_content: bool = True  # reviewer pass scores each format vs brand voice


class CarouselExportPDFRequest(BaseModel):
    subject: str
    content: str
    format_label: Optional[str] = "TPDL Report"


class DeckExportPPTXRequest(BaseModel):
    subject: str
    content: str
    format_label: Optional[str] = "TPDL Deck"


FORMAT_PROMPTS = {
    "linkedin": (
        "Generate a LinkedIn carousel (6-8 slides) on the subject below.\n"
        "Use your strict LinkedIn carousel structure: SLIDE 1 hook, slides 2-N one idea each, "
        "final slide CTA, 3 hashtags. Max 200 chars per slide body. Be punchy and visual.\n\n"
        "Subject: {subject}\n"
        "Additional context: {context}\n\n"
        "Output ONLY the carousel slides in your defined format."
    ),
    "pdf_a4": (
        "Generate a detailed PDF A4 analytical report on the subject below.\n"
        "Use your strict PDF A4 structure: TITLE, SUBTITLE, 4 sections with full prose "
        "(400-600 words each for sections 1-3, 200 words for TPDL PERSPECTIVE), and a CTA.\n"
        "Be analytical, cite realistic data points, use [STAT TO VERIFY] where needed.\n\n"
        "Subject: {subject}\n"
        "Additional context: {context}\n\n"
        "Output ONLY the PDF A4 content in your defined format."
    ),
    "website": (
        "Generate a website article on the subject below.\n"
        "Use your strict website article structure: META TITLE, META DESCRIPTION, H1, INTRO, "
        "3 H2 sections with body text, CTA. SEO-optimised. Accessible, structured.\n\n"
        "Subject: {subject}\n"
        "Additional context: {context}\n\n"
        "Output ONLY the article content in your defined format."
    ),
    "ppt": (
        "Generate a PowerPoint deck outline on the subject below.\n"
        "Use your strict PPT structure: 6-10 slides with TITLE, bullet points per slide, "
        "and a speaker note for each. Executive-ready, clear, no filler slides.\n\n"
        "Subject: {subject}\n"
        "Additional context: {context}\n\n"
        "Output ONLY the PPT outline in your defined format."
    ),
}

FORMAT_LABELS = {
    "linkedin": "LinkedIn Carousel",
    "pdf_a4":   "PDF A4 — Detailed Analysis",
    "website":  "Website Article",
    "ppt":      "PowerPoint Deck",
}

VALID_FORMATS = set(FORMAT_PROMPTS.keys())


# ---- LinkedIn ----------------------------------------------------------------
# Drafts are now persisted in the linkedin_drafts table. The first call seeds
# the table from the V1 mock list so existing content carries over.


def _seed_drafts_if_empty(db: Session) -> None:
    from app.models import LinkedInDraft
    if db.query(LinkedInDraft.id).first() is not None:
        return
    from datetime import datetime
    for d in linkedin_drafts.LINKEDIN_DRAFTS:
        db.add(LinkedInDraft(
            id=d["id"],
            topic=d["topic"],
            angle=d.get("angle", ""),
            author=d.get("author", "marc"),
            status=d.get("status", "pending"),
            preview=d.get("preview", ""),
            full_text=d.get("full_text", ""),
            created_at=datetime.fromisoformat(d["created_at"]),
        ))
    db.commit()
    logger.info("[marketing] seeded %d drafts into DB", len(linkedin_drafts.LINKEDIN_DRAFTS))


def _serialize_draft(d) -> dict:
    return {
        "id": d.id,
        "topic": d.topic,
        "angle": d.angle,
        "author": d.author,
        "status": d.status,
        "preview": d.preview,
        "full_text": d.full_text,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }


@router.get("/linkedin/drafts")
def list_linkedin_drafts(status: str = "pending", db: Session = Depends(get_db)) -> list[dict]:
    from app.models import LinkedInDraft
    _seed_drafts_if_empty(db)
    q = db.query(LinkedInDraft)
    if status != "all":
        q = q.filter(LinkedInDraft.status == status)
    rows = q.order_by(LinkedInDraft.created_at.desc()).all()
    return [_serialize_draft(d) for d in rows]


def _set_draft_status(draft_id: str, new_status: str, db: Session) -> dict:
    from app.models import LinkedInDraft
    draft = db.get(LinkedInDraft, draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail=f"Draft '{draft_id}' not found")
    draft.status = new_status
    db.commit()
    db.refresh(draft)

    # Feed the brand memory loop — approvals become "top performers" examples,
    # rejections teach Marc what to avoid.
    try:
        from app.tools.memory import record_feedback
        record_feedback(
            subject=draft.topic,
            format_id="linkedin",
            decision=new_status,
            content_preview=draft.full_text,
        )
    except Exception as exc:
        logger.warning("[marketing] feedback recording failed: %s", exc)

    return _serialize_draft(draft)


@router.post("/linkedin/drafts/{draft_id}/approve")
def approve_draft(draft_id: str, db: Session = Depends(get_db)) -> dict:
    return _set_draft_status(draft_id, "approved", db)


@router.post("/linkedin/drafts/{draft_id}/reject")
def reject_draft(draft_id: str, db: Session = Depends(get_db)) -> dict:
    return _set_draft_status(draft_id, "rejected", db)


@router.get("/linkedin/metrics")
def linkedin_metrics() -> dict:
    return {
        "kpis": marketing.LINKEDIN_KPIS,
        "series": marketing.engagement_series_30d(),
    }


# ---- Case studies / Website / Outreach ---------------------------------------


@router.get("/case-studies")
def list_case_studies() -> list[dict]:
    return list(marketing.CASE_STUDIES)


@router.get("/website-pages")
def list_website_pages() -> list[dict]:
    return list(marketing.WEBSITE_PAGES)


@router.get("/outreach")
def outreach() -> dict:
    return {
        "pipeline": list(marketing.OUTREACH_PIPELINE),
        "templates": list(marketing.ICP_TEMPLATES),
    }


# ---- Newsletter editorial calendar --------------------------------------------
# Editions live in the newsletter_editions table; the first call seeds the
# 9-edition plan (was hardcoded in marketing.js).

EDITIONS_SEED = [
    dict(number=1, season="s1", season_label="S1 · Who we are", date="2026-06-20",
         title="Why TPDL exists", angle="Our story, our conviction, what we see that others miss",
         edition_type="Founding", format="Short email + PDF download"),
    dict(number=2, season="s1", season_label="S1 · Who we are", date="2026-07-24",
         title="What makes us different", angle="Our method, our angle — not a standard consulting firm",
         edition_type="Positioning", format="Short email + PDF download"),
    dict(number=3, season="s1", season_label="S1 · Who we are", date="2026-08-21",
         title="The 3 pain points we solve", angle="Concrete, quantified, with a mini case study per pain point",
         edition_type="Pain points", format="Short email + PDF download"),
    dict(number=4, season="s2", season_label="S2 · Sector insights", date="2026-09-18",
         title="Education & digital transformation", angle="Business schools, medical schools — why they fall behind",
         edition_type="Analysis", format="Article email + PDF deep-dive"),
    dict(number=5, season="s2", season_label="S2 · Sector insights", date="2026-10-16",
         title="The real cost of a bad C-suite hire", angle="Anonymised case study + downloadable evaluation grid",
         edition_type="Case study", format="Short email + PDF download"),
    dict(number=6, season="s2", season_label="S2 · Sector insights", date="2026-11-20",
         title="PE & M&A: what due diligences miss", angle="Signal detection, timing, common blind spots",
         edition_type="Thought leadership", format="Article email + PDF deep-dive"),
    dict(number=7, season="s3", season_label="S3 · Community", date="2026-12-18",
         title="5 trends for 2027 we're watching", angle="Predictions + why they matter for our clients",
         edition_type="Annual", format="Short email + PDF download"),
    dict(number=8, season="s3", season_label="S3 · Community", date="2027-01-22",
         title="Community voices", angle="Interview with a contact/client, their sector perspective",
         edition_type="Guest", format="Email interview format"),
    dict(number=9, season="s3", season_label="S3 · Community", date="2027-02-19",
         title="6 months of signals — what we found", angle="What we detected, what was confirmed — transparency report",
         edition_type="Retrospective", format="Short email + PDF download"),
]

VALID_EDITION_STATUSES = {"planned", "draft", "review", "published"}


class EditionPatch(BaseModel):
    title:  Optional[str] = None
    angle:  Optional[str] = None
    date:   Optional[str] = None
    status: Optional[str] = None
    edition_type: Optional[str] = None
    format: Optional[str] = None


class EditionCreate(BaseModel):
    title:  str
    date:   str                      # yyyy-mm-dd
    season: str = "s1"
    angle:  str = ""
    edition_type: str = ""
    format: str = "Short email + PDF download"


def _seed_editions_if_empty(db: Session) -> None:
    from app.models import NewsletterEdition
    if db.query(NewsletterEdition.id).first() is not None:
        return
    for e in EDITIONS_SEED:
        db.add(NewsletterEdition(**e))
    db.commit()
    logger.info("[marketing] seeded %d newsletter editions into DB", len(EDITIONS_SEED))


def _serialize_edition(e) -> dict:
    return {
        "id": e.id, "number": e.number, "season": e.season,
        "seasonLabel": e.season_label, "date": e.date, "title": e.title,
        "angle": e.angle, "type": e.edition_type, "format": e.format,
        "status": e.status,
    }


@router.get("/newsletter/editions")
def list_editions(db: Session = Depends(get_db)) -> list[dict]:
    from app.models import NewsletterEdition
    _seed_editions_if_empty(db)
    rows = db.query(NewsletterEdition).order_by(NewsletterEdition.date.asc()).all()
    return [_serialize_edition(e) for e in rows]


@router.patch("/newsletter/editions/{edition_id}")
def update_edition(edition_id: int, patch: EditionPatch, db: Session = Depends(get_db)) -> dict:
    from app.models import NewsletterEdition
    e = db.get(NewsletterEdition, edition_id)
    if e is None:
        raise HTTPException(status_code=404, detail=f"Edition {edition_id} not found")
    if patch.status is not None and patch.status not in VALID_EDITION_STATUSES:
        raise HTTPException(status_code=422, detail=f"Invalid status. Valid: {sorted(VALID_EDITION_STATUSES)}")
    updates = patch.model_dump(exclude_none=True)
    if "edition_type" in updates:
        e.edition_type = updates.pop("edition_type")
    for key, value in updates.items():
        setattr(e, key, value)
    db.commit()
    db.refresh(e)
    return _serialize_edition(e)


@router.post("/newsletter/editions")
def create_edition(req: EditionCreate, db: Session = Depends(get_db)) -> dict:
    from app.models import NewsletterEdition
    max_number = max(
        (n for (n,) in db.query(NewsletterEdition.number).all()), default=0
    )
    season_labels = {"s1": "S1 · Who we are", "s2": "S2 · Sector insights", "s3": "S3 · Community"}
    e = NewsletterEdition(
        number=max_number + 1,
        season=req.season,
        season_label=season_labels.get(req.season, req.season),
        date=req.date,
        title=req.title,
        angle=req.angle,
        edition_type=req.edition_type,
        format=req.format,
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return _serialize_edition(e)


@router.delete("/newsletter/editions/{edition_id}")
def delete_edition(edition_id: int, db: Session = Depends(get_db)) -> dict:
    from app.models import NewsletterEdition
    e = db.get(NewsletterEdition, edition_id)
    if e is None:
        raise HTTPException(status_code=404, detail=f"Edition {edition_id} not found")
    db.delete(e)
    db.commit()
    return {"deleted": edition_id}


# ---- Carousel Studio ---------------------------------------------------------

def _validate_carousel_request(req: CarouselGenerateRequest) -> None:
    invalid = [f for f in req.formats if f not in VALID_FORMATS]
    if invalid:
        raise ValueError(f"Unknown format(s): {invalid}. Valid: {list(VALID_FORMATS)}")
    if not req.formats:
        raise ValueError("At least one format must be selected.")
    if not req.subject.strip():
        raise ValueError("Subject cannot be empty.")


async def _run_carousel_generation(req: CarouselGenerateRequest) -> dict:
    """Core generation — web search in a worker thread, all formats in
    parallel, reviewer scoring per format. Manages its own DB sessions so it
    can run inline (sync endpoint) or as a background job."""
    import asyncio

    from app.agents.base import get_async_anthropic_client
    from app.config import AgentID, settings
    from app.database import SessionLocal
    from app.models import Agent

    _validate_carousel_request(req)

    with SessionLocal() as db:
        marc = db.get(Agent, AgentID.MARC.value)
        if marc is None:
            raise ValueError("Marc agent not found — run `make seed`.")
        marc_system_prompt = marc.system_prompt

    if not settings.anthropic_api_key or settings.anthropic_api_key == "not-set":
        raise RuntimeError("ANTHROPIC_API_KEY is not set.")

    # Optional: enrich with live web search — in a worker thread, off the event loop
    search_context = ""
    if req.web_search:
        try:
            from app.tools.web_search import build_search_context
            logger.info("[carousel] running web search for: %s", req.subject)
            search_context = await asyncio.to_thread(
                build_search_context,
                subject=req.subject,
                sector_hint=req.context or "pharma life sciences",
            )
            logger.info("[carousel] search context: %d chars", len(search_context))
        except Exception as exc:
            logger.warning("[carousel] web search failed (non-blocking): %s", exc)

    # Inject brand memory
    from app.tools.memory import get_brand_voice_block, record_subject
    memory_block = "\n\n" + get_brand_voice_block()

    client = get_async_anthropic_client()
    context = req.context or "Life Sciences / pharma sector. TPDL audience: VP and C-suite in pharma, medtech, dental."
    system_prompt = marc_system_prompt
    search_block = f"\n\n{search_context}" if search_context else ""

    async def _generate(fmt: str) -> tuple[str, dict]:
        prompt = FORMAT_PROMPTS[fmt].format(
            subject=req.subject.strip(),
            context=context,
        ) + search_block + memory_block
        try:
            response = await client.messages.create(
                model=settings.anthropic_model,
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2048,
            )
            text = "".join(
                block.text for block in response.content
                if getattr(block, "type", "") == "text"
            )
            result = {
                "label": FORMAT_LABELS[fmt],
                "content": text.strip(),
                "tokens": response.usage.output_tokens,
            }
            # Reviewer pass — scores the draft against the brand voice.
            # Runs inside this coroutine, so formats still complete in parallel.
            if req.score_content and result["content"]:
                from app.tools.content_score import score_content
                result["review"] = await score_content(
                    content=result["content"],
                    format_label=FORMAT_LABELS[fmt],
                    subject=req.subject,
                )
            return fmt, result
        except Exception as exc:
            logger.exception("[carousel] generation failed for format %s", fmt)
            return fmt, {
                "label": FORMAT_LABELS[fmt],
                "content": None,
                "error": str(exc),
            }

    # All formats in parallel
    pairs = await asyncio.gather(*[_generate(fmt) for fmt in req.formats])
    results = dict(pairs)

    # Record subject in memory
    try:
        record_subject(req.subject, req.formats)
    except Exception as exc:
        logger.warning("[carousel] could not record subject in memory: %s", exc)

    # LinkedIn output also lands in the validation queue (drafts list)
    if results.get("linkedin", {}).get("content"):
        try:
            import uuid
            from app.models import LinkedInDraft
            text = results["linkedin"]["content"]
            with SessionLocal() as db:
                db.add(LinkedInDraft(
                    id=f"draft-{uuid.uuid4().hex[:8]}",
                    topic=req.subject.strip()[:250],
                    angle="carousel",
                    author="marc",
                    status="pending",
                    preview=text[:140],
                    full_text=text,
                ))
                db.commit()
        except Exception as exc:
            logger.warning("[carousel] could not queue LinkedIn draft: %s", exc)

    return {
        "subject": req.subject,
        "formats": req.formats,
        "results": results,
        "search_enriched": bool(search_context),
    }


@router.post("/carousel/generate")
async def generate_carousel(req: CarouselGenerateRequest) -> dict:
    """Inline generation — holds the request open until done (kept for
    compatibility). Prefer /carousel/generate-async + job polling."""
    try:
        return await _run_carousel_generation(req)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


# ---- Generation job queue ------------------------------------------------------

def _serialize_job(j) -> dict:
    import json as _json
    result = None
    if j.status == "done" and j.result:
        try:
            result = _json.loads(j.result)
        except ValueError:
            result = None
    return {
        "id": j.id,
        "kind": j.kind,
        "subject": j.subject,
        "status": j.status,
        "error": j.error,
        "result": result,
        "created_at": j.created_at.isoformat() if j.created_at else None,
        "finished_at": j.finished_at.isoformat() if j.finished_at else None,
    }


def _set_job(job_id: int, **fields) -> None:
    from app.database import SessionLocal
    from app.models import GenerationJob
    with SessionLocal() as db:
        job = db.get(GenerationJob, job_id)
        if job is None:
            return
        for key, value in fields.items():
            setattr(job, key, value)
        db.commit()


async def _run_carousel_job(job_id: int, req: CarouselGenerateRequest) -> None:
    import json as _json
    from datetime import datetime, timezone

    def _utcnow():
        return datetime.now(timezone.utc).replace(tzinfo=None)

    _set_job(job_id, status="running")
    try:
        result = await _run_carousel_generation(req)
        _set_job(job_id, status="done", result=_json.dumps(result), finished_at=_utcnow())
        logger.info("[jobs] job %d done", job_id)
    except Exception as exc:
        logger.exception("[jobs] job %d failed", job_id)
        _set_job(job_id, status="error", error=str(exc), finished_at=_utcnow())


# Strong references to in-flight jobs — asyncio only keeps weak refs to tasks,
# so without this a running job could be garbage-collected mid-generation.
_background_jobs: set = set()


@router.post("/carousel/generate-async")
async def generate_carousel_async(req: CarouselGenerateRequest) -> dict:
    """Submit a generation job and return immediately. Poll /jobs/{id}."""
    import asyncio

    from app.database import SessionLocal
    from app.models import GenerationJob

    try:
        _validate_carousel_request(req)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    with SessionLocal() as db:
        job = GenerationJob(
            kind="carousel",
            subject=req.subject.strip()[:250],
            payload=req.model_dump_json(),
            status="queued",
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        job_id = job.id

    task = asyncio.create_task(_run_carousel_job(job_id, req))
    _background_jobs.add(task)
    task.add_done_callback(_background_jobs.discard)
    return {"job_id": job_id, "status": "queued"}


@router.get("/jobs")
def list_jobs(limit: int = 10, db: Session = Depends(get_db)) -> list[dict]:
    from app.models import GenerationJob
    rows = (
        db.query(GenerationJob)
        .order_by(GenerationJob.id.desc())
        .limit(min(limit, 50))
        .all()
    )
    return [_serialize_job(j) for j in rows]


@router.get("/jobs/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db)) -> dict:
    from app.models import GenerationJob
    job = db.get(GenerationJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return _serialize_job(job)


# ---- PDF Export --------------------------------------------------------------

@router.post("/carousel/export-pdf")
def export_carousel_pdf(req: CarouselExportPDFRequest) -> object:
    """Convert Marc's text output into a branded TPDL A4 PDF."""
    from fastapi.responses import Response
    from app.tools.pdf_export import generate_pdf

    if not req.content.strip():
        raise HTTPException(status_code=422, detail="Content cannot be empty.")

    try:
        pdf_bytes = generate_pdf(
            subject=req.subject,
            content=req.content,
            format_label=req.format_label or "TPDL Report",
        )
    except Exception as exc:
        logger.exception("[pdf_export] generation failed")
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {exc}")

    # Filename goes into the Content-Disposition HTTP header, which must be
    # Latin-1 — strip non-ASCII so a Unicode subject (e.g. "→") can't 500 the export.
    slug = (req.subject[:40].replace(" ", "_").replace("/", "-")
            .encode("ascii", "ignore").decode() or "export")
    filename = f"TPDL_{slug}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/deck/export-pptx")
def export_deck_pptx(req: DeckExportPPTXRequest) -> object:
    """Render Oliver's slide outline into a branded TPDL .pptx deck."""
    from fastapi.responses import Response
    from app.tools.pptx_export import generate_pptx

    if not req.content.strip():
        raise HTTPException(status_code=422, detail="Content cannot be empty.")

    try:
        pptx_bytes = generate_pptx(
            subject=req.subject,
            content=req.content,
            format_label=req.format_label or "TPDL Deck",
        )
    except Exception as exc:
        logger.exception("[pptx_export] generation failed")
        raise HTTPException(status_code=500, detail=f"PPTX generation failed: {exc}")

    # Filename goes into the Content-Disposition HTTP header, which must be
    # Latin-1 — strip non-ASCII so a Unicode subject (e.g. "→") can't 500 the export.
    slug = (req.subject[:40].replace(" ", "_").replace("/", "-")
            .encode("ascii", "ignore").decode() or "export")
    filename = f"TPDL_{slug}.pptx"
    return Response(
        content=pptx_bytes,
        media_type=(
            "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        ),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
