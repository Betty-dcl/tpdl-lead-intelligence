"""Performance analytics — aggregates data from tasks, activity_log, conversations, messages."""
import json
import logging
import re
from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ActivityLog, Agent, Conversation, Message, Task

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/performance", tags=["performance"])

# Marketing Intelligence pipeline
MARKETING_AGENTS = {"iris", "marc", "oliver"}
# Sales / Outbound Intelligence pipeline
INTEL_AGENTS     = {"hugo", "maya", "ines", "julie"}

# Map action codes → readable labels
ACTION_LABELS = {
    "drafted_post":        "LinkedIn draft",
    "structured_case_study": "Case study",
    "scanned_trends":      "Trend scan",
    "monitored_news":      "News scan",
    "scanned_linkedin":    "LinkedIn scan",
    "responded_to_user":   "Chat reply",
    "ran_command":         "Command run",
}


def _days_series(days: int = 30) -> list[str]:
    """Return ISO date strings for the last N days."""
    today = datetime.now(timezone.utc).date()
    return [(today - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]


# ── KPI summary ───────────────────────────────────────────────────────────────

@router.get("/summary")
def summary(db: Session = Depends(get_db)) -> dict:
    total_tasks        = db.query(func.count(Task.id)).scalar() or 0
    total_convs        = db.query(func.count(Conversation.id)).scalar() or 0
    total_messages     = db.query(func.count(Message.id)).filter(Message.role == "user").scalar() or 0
    total_activities   = db.query(func.count(ActivityLog.id)).scalar() or 0

    marketing_tasks = (
        db.query(func.count(Task.id))
        .filter(Task.agent_id.in_(MARKETING_AGENTS))
        .scalar() or 0
    )
    intel_tasks = (
        db.query(func.count(Task.id))
        .filter(Task.agent_id.in_(INTEL_AGENTS))
        .scalar() or 0
    )

    # Last 7 days activity
    since_7d = datetime.now(timezone.utc) - timedelta(days=7)
    recent_activities = (
        db.query(func.count(ActivityLog.id))
        .filter(ActivityLog.created_at >= since_7d)
        .scalar() or 0
    )

    return {
        "total_tasks":        total_tasks,
        "total_conversations": total_convs,
        "user_messages":      total_messages,
        "total_activities":   total_activities,
        "marketing_tasks":    marketing_tasks,
        "intel_tasks":        intel_tasks,
        "recent_7d":          recent_activities,
    }


# ── Activity by agent ─────────────────────────────────────────────────────────

@router.get("/by-agent")
def by_agent(db: Session = Depends(get_db)) -> list[dict]:
    agents = db.query(Agent).all()

    # Batched aggregates — 4 GROUP BY queries total instead of 4 per agent
    task_counts = dict(
        db.query(Task.agent_id, func.count(Task.id)).group_by(Task.agent_id).all()
    )
    conv_counts = dict(
        db.query(Conversation.agent_id, func.count(Conversation.id))
        .group_by(Conversation.agent_id).all()
    )
    msg_counts = dict(
        db.query(Conversation.agent_id, func.count(Message.id))
        .join(Message, Message.conversation_id == Conversation.id)
        .filter(Message.role == "assistant")
        .group_by(Conversation.agent_id).all()
    )
    last_actives = dict(
        db.query(ActivityLog.agent_id, func.max(ActivityLog.created_at))
        .group_by(ActivityLog.agent_id).all()
    )

    rows = []
    for agent in agents:
        task_count  = task_counts.get(agent.id, 0)
        conv_count  = conv_counts.get(agent.id, 0)
        msg_count   = msg_counts.get(agent.id, 0)
        last_active = last_actives.get(agent.id)
        rows.append({
            "id":           agent.id,
            "name":         agent.name,
            "role":         agent.role,
            "color":        agent.color,
            "avatar_seed":  agent.avatar_seed,
            "tasks":        task_count,
            "conversations": conv_count,
            "messages":     msg_count,
            "last_active":  last_active.isoformat() if last_active else None,
            "team":         "marketing" if agent.id in MARKETING_AGENTS else
                            "intel"     if agent.id in INTEL_AGENTS else "management",
        })
    rows.sort(key=lambda r: r["tasks"] + r["messages"], reverse=True)
    return rows


# ── Action breakdown ──────────────────────────────────────────────────────────

@router.get("/actions")
def actions(db: Session = Depends(get_db)) -> list[dict]:
    rows = (
        db.query(ActivityLog.action, func.count(ActivityLog.id).label("count"))
        .group_by(ActivityLog.action)
        .order_by(text("count DESC"))
        .all()
    )
    return [
        {"action": r.action, "label": ACTION_LABELS.get(r.action, r.action), "count": r.count}
        for r in rows
    ]


# ── Activity over time (last 30 days) ─────────────────────────────────────────

@router.get("/timeline")
def timeline(db: Session = Depends(get_db)) -> dict:
    series = _days_series(30)
    # All activity
    all_rows = (
        db.query(
            func.date(ActivityLog.created_at).label("day"),
            func.count(ActivityLog.id).label("count"),
        )
        .group_by(text("day"))
        .all()
    )
    all_map = {str(r.day): r.count for r in all_rows}

    # Marketing only
    mkt_rows = (
        db.query(
            func.date(ActivityLog.created_at).label("day"),
            func.count(ActivityLog.id).label("count"),
        )
        .filter(ActivityLog.agent_id.in_(MARKETING_AGENTS))
        .group_by(text("day"))
        .all()
    )
    mkt_map = {str(r.day): r.count for r in mkt_rows}

    return {
        "labels":    series,
        "all":       [all_map.get(d, 0) for d in series],
        "marketing": [mkt_map.get(d, 0) for d in series],
    }


# ── Top subjects from task titles ─────────────────────────────────────────────

@router.get("/subjects")
def subjects(db: Session = Depends(get_db)) -> list[dict]:
    titles = db.query(Task.title).filter(Task.agent_id.in_(MARKETING_AGENTS)).all()
    STOP = {
        "linkedin", "post", "draft", "case", "study", "website", "page",
        "scan", "trend", "news", "no", "a", "the", "and", "for", "in",
        "of", "to", "on", "with", "from", "—", "-", "·", "topic",
    }
    words: list[str] = []
    for (title,) in titles:
        for word in re.split(r"[\s/\-–—]+", title.lower()):
            w = re.sub(r"[^a-z0-9]", "", word)
            if w and w not in STOP and len(w) > 3:
                words.append(w)
    counted = Counter(words).most_common(12)
    return [{"word": w, "count": c} for w, c in counted]


# ── Content produced breakdown ────────────────────────────────────────────────

@router.get("/content-types")
def content_types(db: Session = Depends(get_db)) -> list[dict]:
    mapping = [
        ("LinkedIn draft",  ["drafted_post"]),
        ("Case study",      ["structured_case_study"]),
        ("Trend scan",      ["scanned_trends"]),
        ("News scan",       ["monitored_news"]),
        ("LinkedIn scan",   ["scanned_linkedin"]),
        ("Chat replies",    ["responded_to_user"]),
    ]
    results = []
    for label, actions_list in mapping:
        count = (
            db.query(func.count(ActivityLog.id))
            .filter(ActivityLog.action.in_(actions_list))
            .scalar() or 0
        )
        results.append({"label": label, "count": count})
    results.sort(key=lambda r: r["count"], reverse=True)
    return results
