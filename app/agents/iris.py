"""Iris — Marketing Research & Trend Scoring (step 1 of the marketing pipeline).

Iris is the marketing-side mix of Hugo + Maya: she runs deep web research on
news/signals/trends by sector AND interprets it — scoring the most interesting
themes of the week to hand to Marc for content.

Slash commands:
  - /research [topic]   → live web research on a topic/sector (raw findings).
  - /trends [sector?]   → research + score the week's most content-worthy themes.
  - /themes             → the scored theme shortlist to hand to Marc.

Web research uses the free DuckDuckGo engine (no key). Theme scoring is done by
Claude. Live re-runs can later be upgraded to the same engines as Hugo (Exa,
Perplexity) once keys are set.
"""
import logging
from typing import Optional

from app.agents.base import BaseAgent
from app.config import AgentID

IRIS_ID: str = AgentID.IRIS.value
logger = logging.getLogger(__name__)


def _research(topic: str) -> str:
    """Run live web research; return a context block (empty string on failure)."""
    try:
        from app.tools.web_search import build_search_context
        return build_search_context(topic, sector_hint="pharma medtech dental marketing")
    except Exception as exc:  # network/library issues are non-fatal
        logger.warning("[iris] research failed for %r: %s", topic, exc)
        return ""


class IrisAgent(BaseAgent):
    def _dispatch_command(self, user_message: str) -> Optional[dict]:
        text = user_message.strip()
        low = text.lower()

        # ── /research [topic] ────────────────────────────────────────────
        if low.startswith("/research"):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                return {
                    "augmented_message": "The user ran `/research` with no topic. Ask what topic or sector to research (e.g. 'CRM in pharma', 'dental DSO consolidation').",
                    "action": "researched",
                    "task_title": "/research (no topic)",
                }
            topic = parts[1].strip()
            ctx = _research(topic)
            if not ctx:
                return {
                    "augmented_message": (
                        f"The user ran `/research {topic}` but live web search returned nothing "
                        f"(network or quota). As Iris, say so and offer to retry or research from "
                        f"what you already know — never fabricate sources."
                    ),
                    "action": "researched",
                    "task_title": f"Research — {topic} (no results)",
                }
            augmented = (
                f"The user ran `/research {topic}`. Here are live web findings:\n\n{ctx}\n\n"
                f"As Iris, synthesise the 4-6 most relevant points for TPDL's audience "
                f"(VP/C-suite in European pharma, medtech, dental), each with its source. "
                f"Then say which of these could become a content theme (hand to Marc via `/trends`)."
            )
            return {
                "augmented_message": augmented,
                "action": "researched",
                "task_title": f"Research — {topic}",
                "metadata": {"topic": topic},
            }

        # ── /trends [sector?]  and  /themes ──────────────────────────────
        if low.startswith("/trends") or low.startswith("/themes"):
            cmd = "/themes" if low.startswith("/themes") else "/trends"
            parts = text.split(maxsplit=1)
            sector = parts[1].strip() if len(parts) > 1 else "pharma medtech dental"
            ctx = _research(f"{sector} industry trends news 2026")
            ctx_block = (f"Live web findings:\n{ctx}\n\n" if ctx else
                         "(Live web search returned nothing — work from known industry context, "
                         "do not fabricate sources.)\n\n")
            augmented = (
                f"The user ran `{cmd} {sector}`. {ctx_block}"
                f"As Iris, identify the most interesting THEMES of the week for {sector} and "
                f"**score each 0-10** on content-worthiness for TPDL's audience (relevance × "
                f"timeliness × differentiation). Return a ranked shortlist: theme — score — "
                f"one-line angle — source if any. Recommend the top 1-2 to hand to Marc for content."
            )
            return {
                "augmented_message": augmented,
                "action": "scored_themes",
                "task_title": f"Themes — {sector}",
                "metadata": {"sector": sector},
            }

        return None
