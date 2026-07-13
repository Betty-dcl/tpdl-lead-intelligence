"""Collaborative workspace API — claim, status, comments, team activity.

Every mutation logs to TeamActivity so the feed shows what the team did.
"""
import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import (
    Comment,
    Company,
    CompanyAssignment,
    CompanyStatus,
    TeamActivity,
    User,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/companies", tags=["companies"])

VALID_STATUSES = (
    "new", "in_review", "outreach_drafted", "sent", "replied", "won", "lost",
)


def _user_summary(u: User) -> dict:
    return {
        "id": u.id,
        "username": u.username,
        "display_name": u.display_name,
        "avatar_seed": u.avatar_seed,
        "color": u.color,
    }


def _ensure_company(db: Session, name: str) -> Company:
    c = db.get(Company, name)
    if c is None:
        raise HTTPException(status_code=404, detail=f"Company '{name}' not found")
    return c


def _log_activity(db: Session, user: User, action: str, company: str, **metadata) -> None:
    db.add(TeamActivity(
        user_id=user.id,
        action=action,
        target_company=company,
        activity_metadata=json.dumps(metadata) if metadata else "{}",
    ))


# ---------------------------------------------------------------------------
# GET /api/companies/{name}/workspace
# Returns assignment + status + comments in one round-trip (used on row expand).
# ---------------------------------------------------------------------------

@router.get("/{name:path}/workspace")
def get_workspace(
    name: str,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
) -> dict:
    _ensure_company(db, name)

    assignment = db.get(CompanyAssignment, name)
    assigned_user = db.get(User, assignment.user_id) if assignment else None

    status_row = db.get(CompanyStatus, name)
    status_val = status_row.status if status_row else "new"
    status_user = db.get(User, status_row.updated_by_user_id) if status_row and status_row.updated_by_user_id else None

    comments = (
        db.query(Comment, User)
        .join(User, User.id == Comment.user_id)
        .filter(Comment.company_name == name)
        .order_by(Comment.created_at.asc())
        .all()
    )

    return {
        "assignment": {
            "user": _user_summary(assigned_user) if assigned_user else None,
            "claimed_at": assignment.claimed_at.isoformat() if assignment else None,
        },
        "status": {
            "value": status_val,
            "updated_by": _user_summary(status_user) if status_user else None,
            "updated_at": status_row.updated_at.isoformat() if status_row else None,
        },
        "comments": [
            {
                "id": c.id,
                "author": _user_summary(u),
                "content": c.content,
                "created_at": c.created_at.isoformat(),
            }
            for c, u in comments
        ],
    }


# ---------------------------------------------------------------------------
# Claim / release
# ---------------------------------------------------------------------------

@router.post("/{name:path}/claim")
def claim(
    name: str,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
) -> dict:
    _ensure_company(db, name)
    existing = db.get(CompanyAssignment, name)
    if existing and existing.user_id != me.id:
        other = db.get(User, existing.user_id)
        raise HTTPException(
            status_code=409,
            detail=f"Already claimed by {other.display_name if other else 'someone else'}",
        )
    if existing is None:
        db.add(CompanyAssignment(company_name=name, user_id=me.id))
    _log_activity(db, me, "claimed", name)
    db.commit()
    return {"ok": True, "user": _user_summary(me)}


@router.post("/{name:path}/release")
def release(
    name: str,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
) -> dict:
    _ensure_company(db, name)
    existing = db.get(CompanyAssignment, name)
    if existing is None:
        return {"ok": True}
    if existing.user_id != me.id:
        raise HTTPException(status_code=403, detail="Only the claimer can release")
    db.delete(existing)
    _log_activity(db, me, "released", name)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

class StatusPayload(BaseModel):
    status: str


@router.post("/{name:path}/status")
def set_status(
    name: str,
    payload: StatusPayload,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
) -> dict:
    _ensure_company(db, name)
    if payload.status not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail=f"Invalid status (allowed: {VALID_STATUSES})")

    row = db.get(CompanyStatus, name)
    old = row.status if row else "new"
    if row is None:
        row = CompanyStatus(company_name=name, status=payload.status, updated_by_user_id=me.id)
        db.add(row)
    else:
        row.status = payload.status
        row.updated_by_user_id = me.id

    _log_activity(db, me, "status_changed", name, from_status=old, to_status=payload.status)
    db.commit()
    return {"ok": True, "status": payload.status}


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------

class CommentPayload(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


@router.post("/{name:path}/comments")
def post_comment(
    name: str,
    payload: CommentPayload,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
) -> dict:
    _ensure_company(db, name)
    c = Comment(company_name=name, user_id=me.id, content=payload.content.strip())
    db.add(c)
    _log_activity(db, me, "commented", name, length=len(c.content))
    db.commit()
    db.refresh(c)
    return {
        "id": c.id,
        "author": _user_summary(me),
        "content": c.content,
        "created_at": c.created_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# Team activity feed (newest first)
# ---------------------------------------------------------------------------

team_router = APIRouter(prefix="/api/team", tags=["team"])


@team_router.get("/activity")
def list_activity(
    limit: int = 30,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
) -> list[dict]:
    limit = max(1, min(limit, 100))
    rows = (
        db.query(TeamActivity, User)
        .join(User, User.id == TeamActivity.user_id)
        .order_by(desc(TeamActivity.id))
        .limit(limit)
        .all()
    )
    out: list[dict] = []
    for a, u in rows:
        try:
            metadata = json.loads(a.activity_metadata or "{}")
        except json.JSONDecodeError:
            metadata = {}
        out.append({
            "id": a.id,
            "user": _user_summary(u),
            "action": a.action,
            "target_company": a.target_company,
            "metadata": metadata,
            "created_at": a.created_at.isoformat(),
        })
    return out


@team_router.get("/users")
def list_users(
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
) -> list[dict]:
    return [_user_summary(u) for u in db.query(User).order_by(User.username).all()]
