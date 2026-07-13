from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Conversation, Message
from app.schemas import MessageOut

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.get("/{conv_id}/messages", response_model=list[MessageOut])
def list_messages(conv_id: int, db: Session = Depends(get_db)) -> list[Message]:
    conv = db.get(Conversation, conv_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return list(
        db.query(Message)
        .filter(Message.conversation_id == conv_id)
        .order_by(Message.id.asc())
        .all()
    )
