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
from app.tools.campaign_themes import find_theme, render_brief
from app.tools.memory import get_brand_dna_block, get_brand_voice_block

MARC_ID: str = AgentID.MARC.value


def _campaign_block(theme: str) -> str:
    """If the free-text theme is one of Iris/Nathalie's campaign themes, hand Marc
    its structured brief (business principle + audience + reframe) so he grounds
    the piece correctly instead of starting blind. Empty string when no match."""
    match = find_theme(theme)
    return f"\n\n{render_brief(match)}" if match else ""


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
                f"The user ran `/angles {theme}`.\n\n{get_brand_dna_block()}\n\n{get_brand_voice_block()}"
                f"{_campaign_block(theme)}\n\n"
                f"As Marc, propose 3-4 DISTINCT content angles for this theme, each tailored to "
                f"TPDL's audience (C-suite/VP in pharma, medtech, dental, surgery). For each: "
                f"angle title — the thesis in one line — why it lands now. Recommend the strongest. "
                f"If a campaign theme match is shown above, every angle must prove that business "
                f"principle and speak to that audience."
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
                f"The user ran `/content {theme}`.\n\n{get_brand_dna_block()}\n\n{get_brand_voice_block()}"
                f"{_campaign_block(theme)}\n\n"
                f"As Marc, write the intelligent content for this theme, grounded in TPDL's brand "
                f"voice and (anonymised) real positioning. If a campaign theme match is shown above, "
                f"START from that business principle (never from a technology) and write for that "
                f"audience. Follow the 7-part doctrine: business principle → the pattern → the "
                f"misdiagnosis → TPDL's principle → evidence → executive implications → takeaway. "
                f"Mark any unconfirmed number as [STAT TO VERIFY] — never invent data, clients or "
                f"results. This is the substance; hand it to Oliver to format (A4 / carousel / PPT / website)."
            )
            return {
                "augmented_message": augmented,
                "action": "wrote_content",
                "task_title": f"Content — {theme[:60]}",
                "metadata": {"theme": theme},
            }

        return None
