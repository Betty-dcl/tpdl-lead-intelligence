"""Marc — Content Architect (step 2 of the marketing pipeline).

From Iris's scored themes + TPDL's brand DNA, Marc writes the intelligent
content for each theme. He owns substance, not layout (that's Oliver).

Slash commands:
  - /angles [theme]   → 3-4 distinct content angles for a theme.
  - /content [theme]   → a full content piece (hook · thesis · argument · CTA).

Grounded in brand memory; never invents data (marks [STAT TO VERIFY]).
"""
from typing import Optional

from app.agents.base import BaseAgent
from app.config import AgentID
from app.tools.memory import get_brand_dna_block, get_brand_voice_block

MARC_ID: str = AgentID.MARC.value


class MarcAgent(BaseAgent):
    def _dispatch_command(self, user_message: str) -> Optional[dict]:
        text = user_message.strip()
        low = text.lower()

        # ── /angles [theme] ──────────────────────────────────────────────
        if low.startswith("/angles"):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                return {
                    "augmented_message": "The user ran `/angles` with no theme. Ask which theme (from Iris) to angle.",
                    "action": "proposed_angles",
                    "task_title": "/angles (no theme)",
                }
            theme = parts[1].strip()
            augmented = (
                f"The user ran `/angles {theme}`.\n\n{get_brand_dna_block()}\n\n{get_brand_voice_block()}\n\n"
                f"As Marc, propose 3-4 DISTINCT content angles for this theme, each tailored to "
                f"TPDL's audience (C-suite/VP in pharma, medtech, dental, surgery). For each: "
                f"angle title — the thesis in one line — why it lands now. Recommend the strongest."
            )
            return {
                "augmented_message": augmented,
                "action": "proposed_angles",
                "task_title": f"Angles — {theme[:60]}",
                "metadata": {"theme": theme},
            }

        # ── /content [theme] ─────────────────────────────────────────────
        if low.startswith("/content"):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                return {
                    "augmented_message": "The user ran `/content` with no theme. Ask which theme to develop into content.",
                    "action": "wrote_content",
                    "task_title": "/content (no theme)",
                }
            theme = parts[1].strip()
            augmented = (
                f"The user ran `/content {theme}`.\n\n{get_brand_dna_block()}\n\n{get_brand_voice_block()}\n\n"
                f"As Marc, write the intelligent content for this theme, grounded in TPDL's brand "
                f"voice and (anonymised) real positioning. Structure: strong hook → thesis → "
                f"argument with concrete points → TPDL angle → clear takeaway. Mark any unconfirmed "
                f"number as [STAT TO VERIFY] — never invent data, clients or results. This is the "
                f"substance; hand it to Oliver to format (A4 / carousel / PPT / website)."
            )
            return {
                "augmented_message": augmented,
                "action": "wrote_content",
                "task_title": f"Content — {theme[:60]}",
                "metadata": {"theme": theme},
            }

        return None
