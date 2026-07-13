"""Oliver — Format Producer (step 3, final, of the marketing pipeline).

Oliver takes Marc's content and renders the final format, brand-consistent.
He owns form, not substance.

Slash commands:
  - /format [type] [theme]  → produce a format. type ∈ a4 | carousel | ppt | website.
  - /carousel [theme]        → shortcut for the LinkedIn carousel.
  - /article [theme]         → shortcut for the A4 long-form article.

Per-format structures are first drafts; exact TPDL templates + the lead-capture
carousel get refined as we form Oliver further.
"""
from typing import Optional

from app.agents.base import BaseAgent
from app.config import AgentID

OLIVER_ID: str = AgentID.OLIVER.value

# TPDL brand: dark green #094752, accent #34D591, clean typography.
FORMAT_SPECS: dict[str, str] = {
    "a4": (
        "A4 LONG-FORM ARTICLE — sophisticated, detailed, professional. Sections with "
        "headings, a strong intro, structured argument, a closing CTA. Keep Marc's substance "
        "intact; produce publication-ready prose."
    ),
    "carousel": (
        "LINKEDIN CAROUSEL — 6-8 slides, one idea per slide, punchy and scannable. "
        "SLIDE 1 = hook; middle slides = one point each; final slide = CTA. Give each slide as "
        "'SLIDE n: <title> / <1-2 lines>'."
    ),
    "ppt": (
        "POWERPOINT DECK — executive-ready. Give a slide-by-slide outline: title slide, agenda, "
        "one key message per slide with supporting bullets, closing slide. Keep it tight."
    ),
    "website": (
        "WEBSITE ARTICLE — clean, structured, SEO-aware. H1 + H2s, short scannable paragraphs, "
        "a meta description, and a CTA block."
    ),
}
_ALIASES = {"/carousel": "carousel", "/article": "a4"}


class OliverAgent(BaseAgent):
    def _dispatch_command(self, user_message: str) -> Optional[dict]:
        text = user_message.strip()
        low = text.lower()

        fmt: Optional[str] = None
        theme = ""

        # shortcuts: /carousel [theme], /article [theme]
        for alias, mapped in _ALIASES.items():
            if low == alias or low.startswith(alias + " "):
                fmt = mapped
                parts = text.split(maxsplit=1)
                theme = parts[1].strip() if len(parts) > 1 else ""
                break

        # /format [type] [theme]
        if fmt is None and low.startswith("/format"):
            parts = text.split(maxsplit=2)
            if len(parts) < 2:
                return {
                    "augmented_message": (
                        "The user ran `/format` with no type. Ask which format: "
                        "a4, carousel, ppt, or website — and for which theme."
                    ),
                    "action": "produced_format",
                    "task_title": "/format (no type)",
                }
            fmt = parts[1].strip().lower()
            theme = parts[2].strip() if len(parts) > 2 else ""

        if fmt is None:
            return None

        if fmt not in FORMAT_SPECS:
            return {
                "augmented_message": (
                    f"The user asked for format '{fmt}', which isn't supported. Valid: "
                    f"a4, carousel, ppt, website. Ask them to pick one."
                ),
                "action": "produced_format",
                "task_title": f"/format {fmt} (invalid)",
            }
        if not theme:
            return {
                "augmented_message": (
                    f"The user wants a {fmt} but gave no theme/content. Ask for Marc's "
                    f"content or the theme to format."
                ),
                "action": "produced_format",
                "task_title": f"/{fmt} (no theme)",
            }

        augmented = (
            f"The user wants a **{fmt.upper()}** for: {theme}\n\n"
            f"FORMAT SPEC: {FORMAT_SPECS[fmt]}\n\n"
            f"TPDL BRANDING: dark green #094752, accent #34D591, clean typography, no AI hype.\n\n"
            f"As Oliver, produce this format. If you don't have Marc's full content, build the "
            f"best version from the theme and note one line on what Marc's content would add. "
            f"Keep substance intact; you own the form."
        )
        return {
            "augmented_message": augmented,
            "action": "produced_format",
            "task_title": f"{fmt.upper()} — {theme[:50]}",
            "metadata": {"format": fmt, "theme": theme},
        }
