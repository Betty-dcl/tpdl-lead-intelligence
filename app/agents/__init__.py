"""Agent registry — maps agent_id to its (possibly specialised) class.

Roster v3 — two pipelines:
  Sales / Outbound Intelligence : hugo → maya → ines → julie
  Marketing Intelligence        : iris → marc → oliver
  Manager                       : Alex (manager)

For now every agent runs on BaseAgent (pure system-prompt chat). As we "form"
each agent we'll give it a dedicated subclass with its own tools / slash
commands (Hugo deep-research, Inès Apollo, Oliver formats, ...) and register it
here.
"""
from app.agents.base import BaseAgent
from app.agents.hugo import HugoAgent
from app.agents.ines import InesAgent
from app.agents.iris import IrisAgent
from app.agents.julie import JulieAgent
from app.agents.marc import MarcAgent
from app.agents.maya import MayaAgent
from app.agents.oliver import OliverAgent

AGENT_CLASSES: dict[str, type[BaseAgent]] = {
    # Custom agent classes get registered here as we build each one's tooling.
    "hugo": HugoAgent,   # Deep Research & Scoring — owns the scored universe
    "maya": MayaAgent,   # Analyst — Top 50/100, trends, recurring
    "ines": InesAgent,   # Contacts & Radars — Apollo + lunch/language/premium
    "julie": JulieAgent, # Segmented Outreach — sector + brand + signal
    "iris": IrisAgent,   # Marketing Research & Trend Scoring
    "marc": MarcAgent,   # Content Architect
    "oliver": OliverAgent, # Format Producer
}


def get_agent_class(agent_id: str) -> type[BaseAgent]:
    return AGENT_CLASSES.get(agent_id, BaseAgent)
