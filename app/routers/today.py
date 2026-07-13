"""Today view — one call that aggregates everything a team member needs
at the start of the day: drafts to validate, next newsletter edition,
latest veille subjects, their assigned companies, recent team activity,
and generation jobs in flight.
"""
import logging
from datetime import date, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import (
    ActivityLog, Agent, CompanyAssignment, CompanyStatus,
    GenerationJob, LinkedInDraft, NewsletterEdition, User,
)
from app.routers.performance import ACTION_LABELS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/today", tags=["today"])


@router.get("")
def today(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    today_iso = date.today().isoformat()

    # ── Drafts pending validation ────────────────────────────────────────
    pending_q = db.query(LinkedInDraft).filter(LinkedInDraft.status == "pending")
    pending_count = pending_q.count()
    pending_top = [
        {"id": d.id, "topic": d.topic, "preview": d.preview,
         "created_at": d.created_at.isoformat() if d.created_at else None}
        for d in pending_q.order_by(LinkedInDraft.created_at.desc()).limit(3).all()
    ]

    # ── Next newsletter edition ──────────────────────────────────────────
    next_ed = (
        db.query(NewsletterEdition)
        .filter(NewsletterEdition.date >= today_iso,
                NewsletterEdition.status != "published")
        .order_by(NewsletterEdition.date.asc())
        .first()
    )
    next_edition = None
    if next_ed:
        days_left = (date.fromisoformat(next_ed.date) - date.today()).days
        next_edition = {
            "id": next_ed.id, "number": next_ed.number, "title": next_ed.title,
            "date": next_ed.date, "status": next_ed.status, "days_left": days_left,
        }

    # ── Latest veille run ────────────────────────────────────────────────
    latest_veille = None
    try:
        from app.tools.memory import get_memory
        runs = get_memory().get("veille_runs", [])
        if runs:
            latest_veille = {
                "date": runs[0].get("date"),
                "subjects": (runs[0].get("subjects") or [])[:3],
            }
    except Exception as exc:
        logger.warning("[today] veille lookup failed: %s", exc)

    # ── My assigned companies ────────────────────────────────────────────
    my_rows = (
        db.query(CompanyAssignment, CompanyStatus)
        .outerjoin(CompanyStatus,
                   CompanyStatus.company_name == CompanyAssignment.company_name)
        .filter(CompanyAssignment.user_id == user.id)
        .order_by(CompanyAssignment.claimed_at.desc())
        .limit(10)
        .all()
    )
    my_companies = [
        {
            "name": a.company_name,
            "status": s.status if s else "new",
            "claimed_at": a.claimed_at.isoformat() if a.claimed_at else None,
        }
        for a, s in my_rows
    ]

    # ── Recent agent activity ────────────────────────────────────────────
    activity_rows = (
        db.query(ActivityLog, Agent)
        .join(Agent, ActivityLog.agent_id == Agent.id)
        .order_by(ActivityLog.id.desc())
        .limit(8)
        .all()
    )
    recent_activity = [
        {
            "agent": agent.name,
            "agent_id": agent.id,
            "avatar_seed": agent.avatar_seed,
            "label": ACTION_LABELS.get(log.action, log.action),
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log, agent in activity_rows
    ]

    # ── Generation jobs in flight / recent ───────────────────────────────
    job_rows = (
        db.query(GenerationJob).order_by(GenerationJob.id.desc()).limit(3).all()
    )
    jobs = [
        {"id": j.id, "subject": j.subject, "status": j.status,
         "created_at": j.created_at.isoformat() if j.created_at else None}
        for j in job_rows
    ]

    return {
        "user": {"username": user.username, "display_name": user.display_name},
        "date": today_iso,
        "pending_drafts": {"count": pending_count, "top": pending_top},
        "next_edition": next_edition,
        "latest_veille": latest_veille,
        "my_companies": my_companies,
        "recent_activity": recent_activity,
        "jobs": jobs,
    }
