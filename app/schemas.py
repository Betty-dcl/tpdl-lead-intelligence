from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    conversation_id: int | None = None
    message: str = Field(min_length=1, max_length=4000)


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    created_at: datetime


class ChatResponse(BaseModel):
    conversation_id: int
    message: MessageOut
    routed_to: str | None = None


class AgentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    role: str
    avatar_seed: str
    color: str
    status: str
    last_activity_label: str | None = None
    last_activity_at: datetime | None = None


class ConversationOut(BaseModel):
    id: int
    agent_id: str
    title: str
    message_count: int
    created_at: datetime
    updated_at: datetime


class ActivityOut(BaseModel):
    id: int
    agent_id: str
    action: str
    label: str
    metadata: dict
    created_at: datetime
