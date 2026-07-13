"""Briefs API — cached specialist outputs per company × agent.

Each row in specialist_outputs is one rendered brief. Lazy generation:
the UI doesn't auto-generate, the user clicks "Generate brief". Result
cached forever until DELETE'd ("re-run").
"""
import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.agents import get_agent_class
from app.agents.base import AgentResponseError
from app.auth import get_current_user
from app.database import get_db
from app.models import Agent, Company, SpecialistOutput, TeamActivity, User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/companies", tags=["briefs"])


def _agent_summary(a: Agent | None) -> dict | None:
    if a is None:
        return None
    return {
        "id": a.id,
        "name": a.name,
        "role": a.role,
        "avatar_seed": a.avatar_seed,
        "color": a.color,
    }


def _user_summary(u: User | None) -> dict | None:
    if u is None:
        return None
    return {
        "id": u.id,
        "display_name": u.display_name,
        "avatar_seed": u.avatar_seed,
    }


def _serialize(brief: SpecialistOutput, agent: Agent | None, user: User | None) -> dict:
    return {
        "id": brief.id,
        "agent": _agent_summary(agent),
        "output": brief.output,
        "generated_at": brief.generated_at.isoformat(),
        "generated_by": _user_summary(user),
    }


def _ensure_company(db: Session, name: str) -> Company:
    c = db.get(Company, name)
    if c is None:
        raise HTTPException(status_code=404, detail=f"Company '{name}' not found")
    return c


@router.get("/{name:path}/briefs")
def list_briefs(
    name: str,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
) -> list[dict]:
    """All cached briefs for that company, newest first per agent."""
    _ensure_company(db, name)
    rows = (
        db.query(SpecialistOutput, Agent, User)
        .join(Agent, Agent.id == SpecialistOutput.agent_id)
        .outerjoin(User, User.id == SpecialistOutput.generated_by_user_id)
        .filter(SpecialistOutput.company_name == name)
        .order_by(desc(SpecialistOutput.generated_at))
        .all()
    )
    return [_serialize(b, a, u) for b, a, u in rows]


@router.get("/{name:path}/briefs/{agent_id}")
def get_brief(
    name: str,
    agent_id: str,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
) -> dict | None:
    """Latest cached brief for that company × agent, or null if none."""
    _ensure_company(db, name)
    row = (
        db.query(SpecialistOutput, Agent, User)
        .join(Agent, Agent.id == SpecialistOutput.agent_id)
        .outerjoin(User, User.id == SpecialistOutput.generated_by_user_id)
        .filter(SpecialistOutput.company_name == name,
                SpecialistOutput.agent_id == agent_id)
        .order_by(desc(SpecialistOutput.generated_at))
        .first()
    )
    if row is None:
        return None
    b, a, u = row
    return _serialize(b, a, u)


@router.post("/{name:path}/briefs/{agent_id}/generate")
def generate_brief(
    name: str,
    agent_id: str,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
) -> dict:
    """Synchronously call Claude through the specialist, cache, return."""
    company = _ensure_company(db, name)
    agent_record = db.get(Agent, agent_id)
    if agent_record is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    # Load specialist instance and run one-shot generation.
    agent_cls = get_agent_class(agent_id)
    agent = agent_cls.load(db, agent_id)

    try:
        text = agent.generate_one_shot(f"/generate {name}")
    except AgentResponseError as exc:
        logger.error("[briefs] generation failed for %s × %s: %s", name, agent_id, exc)
        raise HTTPException(status_code=502, detail=str(exc))

    # Cache.
    brief = SpecialistOutput(
        company_name=name,
        agent_id=agent_id,
        output=text,
        generated_by_user_id=me.id,
    )
    db.add(brief)

    # Log to team activity.
    db.add(TeamActivity(
        user_id=me.id,
        action="generated_brief",
        target_company=name,
        activity_metadata=json.dumps({
            "agent_id": agent_id,
            "agent_name": agent_record.name,
        }),
    ))

    db.commit()
    db.refresh(brief)
    return _serialize(brief, agent_record, me)


@router.delete("/{name:path}/briefs/{agent_id}")
def delete_brief(
    name: str,
    agent_id: str,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
) -> dict:
    """Drop all cached briefs for that company × agent. Next call re-runs Claude."""
    _ensure_company(db, name)
    rows = (
        db.query(SpecialistOutput)
        .filter(SpecialistOutput.company_name == name,
                SpecialistOutput.agent_id == agent_id)
        .all()
    )
    n = len(rows)
    for r in rows:
        db.delete(r)
    db.commit()
    return {"ok": True, "deleted": n}
