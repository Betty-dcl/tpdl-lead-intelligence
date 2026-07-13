import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.activity_labels import label_for
from app.database import get_db
from app.models import ActivityLog, Agent, Conversation, Message

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("")
def list_agents(db: Session = Depends(get_db)) -> list[dict]:
    agents = db.query(Agent).order_by(Agent.created_at.asc()).all()

    # Per-agent latest activity (subquery: max(id) per agent_id, then join).
    latest_ids_sq = (
        db.query(ActivityLog.agent_id, func.max(ActivityLog.id).label("max_id"))
        .group_by(ActivityLog.agent_id)
        .subquery()
    )
    latest_rows = (
        db.query(ActivityLog)
        .join(latest_ids_sq, ActivityLog.id == latest_ids_sq.c.max_id)
        .all()
    )
    latest_by_agent = {r.agent_id: r for r in latest_rows}

    out: list[dict] = []
    for a in agents:
        act = latest_by_agent.get(a.id)
        out.append({
            "id": a.id,
            "name": a.name,
            "role": a.role,
            "avatar_seed": a.avatar_seed,
            "color": a.color,
            "status": a.status,
            "last_activity_label": label_for(act.action) if act else None,
            "last_activity_at": act.created_at if act else None,
        })
    return out


@router.get("/{agent_id}")
def get_agent(agent_id: str, db: Session = Depends(get_db)) -> dict:
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    return {
        "id": agent.id,
        "name": agent.name,
        "role": agent.role,
        "avatar_seed": agent.avatar_seed,
        "color": agent.color,
        "status": agent.status,
    }


@router.get("/{agent_id}/conversations")
def list_conversations(agent_id: str, db: Session = Depends(get_db)) -> list[dict]:
    if db.get(Agent, agent_id) is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    rows = (
        db.query(
            Conversation.id,
            Conversation.agent_id,
            Conversation.title,
            Conversation.created_at,
            Conversation.updated_at,
            func.count(Message.id).label("message_count"),
        )
        .outerjoin(Message, Message.conversation_id == Conversation.id)
        .filter(Conversation.agent_id == agent_id)
        .group_by(Conversation.id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "agent_id": r.agent_id,
            "title": r.title,
            "message_count": r.message_count,
            "created_at": r.created_at,
            "updated_at": r.updated_at,
        }
        for r in rows
    ]


@router.get("/{agent_id}/activity")
def list_activity(
    agent_id: str, limit: int = 20, db: Session = Depends(get_db)
) -> list[dict]:
    if db.get(Agent, agent_id) is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    limit = max(1, min(limit, 100))

    rows = (
        db.query(ActivityLog)
        .filter(ActivityLog.agent_id == agent_id)
        .order_by(ActivityLog.id.desc())
        .limit(limit)
        .all()
    )
    out: list[dict] = []
    for r in rows:
        try:
            metadata = json.loads(r.activity_metadata or "{}")
        except json.JSONDecodeError:
            metadata = {}
        out.append({
            "id": r.id,
            "agent_id": r.agent_id,
            "action": r.action,
            "label": label_for(r.action),
            "metadata": metadata,
            "created_at": r.created_at,
        })
    return out
