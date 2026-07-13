import json
import logging
import re
from typing import Optional

from anthropic import Anthropic, AsyncAnthropic, APIError
from sqlalchemy import func, update
from sqlalchemy.orm import Session

from app.config import settings
from app.models import ActivityLog, Agent, Conversation, Message, Task

logger = logging.getLogger(__name__)

ROUTE_RE = re.compile(r"\[ROUTE_TO:\s*([a-zA-Z0-9_-]+)\s*\]", re.IGNORECASE)
MAX_HISTORY_MESSAGES = 30
# Agents produce full briefs, ranked lists, outreach drafts and long-form content
# (Oliver's A4 article, Marc's content pieces). 1024 truncated these mid-output.
# 8192 covers every agent's deliverable and stays well under the non-streaming
# HTTP-timeout ceiling (~16k). max_tokens is a cap, not a target — no extra cost
# for short replies (e.g. Alex's 2-3 sentence routing).
DEFAULT_MAX_TOKENS = 8192

_anthropic_client: Anthropic | None = None
_async_anthropic_client: AsyncAnthropic | None = None


class AgentNotFoundError(ValueError):
    pass


class AgentResponseError(RuntimeError):
    pass


def extract_route(text: str) -> tuple[str, Optional[str]]:
    """Strip a [ROUTE_TO: agent_id] tag and return (clean_text, agent_id_or_None)."""
    m = ROUTE_RE.search(text)
    if not m:
        return text.strip(), None
    cleaned = ROUTE_RE.sub("", text).strip()
    return cleaned, m.group(1).lower()


def get_anthropic_client() -> Anthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = Anthropic(api_key=settings.anthropic_api_key)
    return _anthropic_client


def get_async_anthropic_client() -> AsyncAnthropic:
    """Async client — lets endpoints run several Claude calls in parallel
    without freezing the server for other users."""
    global _async_anthropic_client
    if _async_anthropic_client is None:
        _async_anthropic_client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _async_anthropic_client


class BaseAgent:
    """Generic agent — handles persistence, history and the Claude call.

    Subclasses override `_dispatch_command` to recognise slash commands. The
    hook returns a dict with up to four keys:
        - augmented_message: str — text sent to Claude in place of the raw user
          input (the raw input is still stored verbatim in `messages`).
        - action: str — value written to activity_log.action.
        - task_title: str — value written to tasks.title.
        - metadata: dict — JSON-serialised payload merged into activity_log.metadata.
    Return None when the message is not a recognised command.
    """

    def __init__(self, db: Session, record: Agent) -> None:
        self.db = db
        self.record = record

    @classmethod
    def load(cls, db: Session, agent_id: str) -> "BaseAgent":
        record = db.get(Agent, agent_id)
        if record is None:
            raise AgentNotFoundError(agent_id)
        return cls(db=db, record=record)

    def _dispatch_command(self, user_message: str) -> Optional[dict]:
        """Override in subclasses."""
        return None

    def respond(self, conversation_id: Optional[int], user_message: str) -> dict:
        conversation = self._get_or_create_conversation(conversation_id, user_message)

        command_meta = self._dispatch_command(user_message)

        # Always store the raw user input — that's what the user typed.
        self.db.add(Message(
            conversation_id=conversation.id,
            role="user",
            content=user_message,
        ))
        self.db.flush()

        history = self._build_history(conversation.id)
        # If the command handler produced an augmented message, swap it in for Claude
        # (the raw message stays in storage for the UI).
        if command_meta and command_meta.get("augmented_message") and history:
            if history[-1]["role"] == "user":
                history[-1]["content"] = command_meta["augmented_message"]

        try:
            text, usage = self._call_claude(history)
        except APIError as exc:
            logger.exception("[%s] Anthropic API error", self.record.id)
            self.db.rollback()
            raise AgentResponseError(str(exc)) from exc

        assistant_msg = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=text,
        )
        self.db.add(assistant_msg)

        if command_meta:
            activity_metadata = {**usage, **(command_meta.get("metadata") or {})}
            self.db.add(ActivityLog(
                agent_id=self.record.id,
                action=command_meta.get("action", "ran_command"),
                activity_metadata=json.dumps(activity_metadata),
            ))
            self.db.add(Task(
                agent_id=self.record.id,
                title=command_meta.get("task_title", "Command"),
                description=user_message,
                status="done",
                output=text,
            ))
        else:
            self.db.add(ActivityLog(
                agent_id=self.record.id,
                action="responded_to_user",
                activity_metadata=json.dumps(usage),
            ))

        self.db.execute(
            update(Conversation)
            .where(Conversation.id == conversation.id)
            .values(updated_at=func.now())
        )

        self.db.commit()
        self.db.refresh(assistant_msg)

        clean_text, routed_to = extract_route(text)

        return {
            "conversation_id": conversation.id,
            "message": {
                "id": assistant_msg.id,
                "role": assistant_msg.role,
                "content": clean_text,
                "created_at": assistant_msg.created_at,
            },
            "routed_to": routed_to,
        }

    def generate_one_shot(self, command: str) -> str:
        """One-shot Claude call — no conversation history, no persistence.

        Used by the workspace 'Generate brief' button: caller passes a
        slash command like '/generate Hologic', we build the augmented
        prompt via _dispatch_command, fire a single message to Claude,
        and return the text. Caller decides whether to cache the result.
        """
        meta = self._dispatch_command(command)
        if meta is None:
            raise AgentResponseError(
                f"Agent {self.record.id} does not handle command: {command}"
            )
        prompt = meta.get("augmented_message") or command
        try:
            text, _usage = self._call_claude([{"role": "user", "content": prompt}])
        except APIError as exc:
            logger.exception("[%s] Anthropic API error (one-shot)", self.record.id)
            raise AgentResponseError(str(exc)) from exc
        clean, _routed = extract_route(text)
        return clean

    def _get_or_create_conversation(
        self, conversation_id: Optional[int], first_message: str
    ) -> Conversation:
        if conversation_id is not None:
            conv = self.db.get(Conversation, conversation_id)
            if conv is None:
                raise AgentNotFoundError(f"conversation {conversation_id}")
            if conv.agent_id != self.record.id:
                raise AgentNotFoundError(
                    f"conversation {conversation_id} belongs to a different agent"
                )
            return conv

        title = (first_message.strip().splitlines() or ["New conversation"])[0][:80]
        conv = Conversation(agent_id=self.record.id, title=title or "New conversation")
        self.db.add(conv)
        self.db.flush()
        return conv

    def _build_history(self, conversation_id: int) -> list[dict]:
        rows = (
            self.db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.id.asc())
            .all()
        )
        history = [
            {"role": m.role, "content": m.content}
            for m in rows[-MAX_HISTORY_MESSAGES:]
            if m.role in ("user", "assistant")
        ]
        # The Anthropic API requires the first message to be `user`. Trimming to
        # the last N can land the window on an assistant turn (odd message count
        # past the cap) → a 400. Drop any leading assistant turns so the window
        # always opens on a user message.
        while history and history[0]["role"] != "user":
            history.pop(0)
        return history

    def _call_claude(self, messages: list[dict]) -> tuple[str, dict]:
        if not settings.anthropic_api_key or settings.anthropic_api_key == "not-set":
            raise AgentResponseError(
                "ANTHROPIC_API_KEY is not set — add it to .env and restart the server."
            )

        client = get_anthropic_client()
        response = client.messages.create(
            model=settings.anthropic_model,
            system=self.record.system_prompt,
            messages=messages,
            max_tokens=DEFAULT_MAX_TOKENS,
        )
        text = "".join(
            block.text for block in response.content if getattr(block, "type", "") == "text"
        )
        usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "model": settings.anthropic_model,
        }
        return text, usage
