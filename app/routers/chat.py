import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents import get_agent_class
from app.agents.base import AgentNotFoundError, AgentResponseError
from app.database import get_db
from app.schemas import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/{agent_id}", response_model=ChatResponse)
def chat(agent_id: str, req: ChatRequest, db: Session = Depends(get_db)) -> dict:
    try:
        agent = get_agent_class(agent_id).load(db, agent_id)
    except AgentNotFoundError:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    try:
        return agent.respond(req.conversation_id, req.message)
    except AgentNotFoundError as exc:
        # respond() → _get_or_create_conversation raises this for a stale/foreign
        # conversation_id — a normal client situation, so 404 not 500.
        raise HTTPException(status_code=404, detail=str(exc))
    except AgentResponseError as exc:
        logger.error("[%s] response failed: %s", agent_id, exc)
        raise HTTPException(
            status_code=502,
            detail=f"{agent.record.name} could not respond — {exc}",
        )
