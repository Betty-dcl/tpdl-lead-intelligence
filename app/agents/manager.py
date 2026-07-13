"""The Manager (Alex) — entry-point router agent.

Behaviour is fully driven by the system prompt seeded in the DB.
The agent uses the generic BaseAgent class; the Manager's only
specialness is the `[ROUTE_TO: agent_id]` tag it emits, which
BaseAgent.respond() extracts and surfaces to the frontend.
"""
from app.config import AgentID

MANAGER_ID: str = AgentID.MANAGER.value
