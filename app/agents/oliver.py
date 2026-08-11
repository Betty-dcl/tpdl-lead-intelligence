"""Oliver — Format Producer (step 3, final, of the marketing pipeline).

Oliver takes Marc's content and renders the final format, brand-consistent.
He owns form, not substance.

Slash commands:
  - /format [type] [theme]  → produce a format. type ∈ a4 | carousel | ppt | website | newsletter.
  - /carousel [theme]        → shortcut for the LinkedIn carousel.
  - /article [theme]         → shortcut for the A4 long-form article.
  - /newsletter [theme]      → shortcut for the MailChimp newsletter (70/10/20 mix).

Per-format structures are first drafts; exact TPDL templates + the lead-capture
carousel get refined as we form Oliver further.
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.agents.base import BaseAgent
from app.config import AgentID
from app.models import Task
from app.tools.campaign_themes import find_theme

OLIVER_ID: str = AgentID.OLIVER.value
_MARC_CONTENT_PREFIX = "Content — "


def find_marc_content(db: Session, theme: str) -> Optional[str]:
    """Most recent Marc `/content` output matching this theme, or None.

    Marc's chat flow persists each /content piece as a Task (agent_id=marc,
    title='Content — <theme>', output=<the piece>). Oliver reads it back so he
    formats Marc's REAL text instead of re-deriving from a bare topic. Match on
    the campaign theme (both route to the same one) or on the theme text
    appearing in Marc's task title. Deterministic DB read, no network."""
    if not theme:
        return None
    wanted = find_theme(theme)
    wanted_norm = theme.strip().lower()
    tasks = (db.query(Task)
             .filter(Task.agent_id == AgentID.MARC.value,
                     Task.title.like(_MARC_CONTENT_PREFIX + "%"),
                     Task.output.isnot(None))
             .order_by(Task.id.desc()).limit(30).all())
    for t in tasks:
        marc_theme = t.title[len(_MARC_CONTENT_PREFIX):].strip()
        marc_match = find_theme(marc_theme)
        if wanted and marc_match and marc_match.key == wanted.key:
            return t.output
        ml = marc_theme.lower()
        if ml and (ml in wanted_norm or wanted_norm in ml):
            return t.output
    return None

# TPDL brand (official charte): near-black #0A0A0A, accent #34D591, Funnel Sans.
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
    "newsletter": (
        "EMAIL NEWSLETTER — feeds MailChimp for Inès's Segment 3 (nurture). Content weighting is "
        "FIXED at ~70% existing-CRM-audience relevance / ~10% LinkedIn trends / ~20% TPDL "
        "strengths & case studies. Structure: 'SUBJECT: <line>' + a one-line preheader, a short "
        "editorial intro, then sections that honour the 70/10/20 mix (label each section with its "
        "bucket, e.g. '[CRM audience]'), and one clear CTA. Scannable, senior tone, no hype."
    ),
}
_ALIASES = {"/carousel": "carousel", "/article": "a4", "/newsletter": "newsletter"}


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
                        "a4, carousel, ppt, website, or newsletter — and for which theme."
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
                    f"a4, carousel, ppt, website, newsletter. Ask them to pick one."
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

        match = find_theme(theme)
        audience_line = (
            f"TARGET AUDIENCE (campaign theme): {match.audience} — prioritise the "
            f"information this audience cares about first.\n\n" if match else ""
        )
        # Pull Marc's actual content for this theme if he has produced it — then
        # Oliver formats the REAL piece rather than re-deriving from the topic.
        marc_content = find_marc_content(self.db, theme)
        if marc_content:
            content_block = (
                f"MARC'S CONTENT — format THIS, do not rewrite the argument:\n"
                f"\"\"\"\n{marc_content}\n\"\"\"\n\n"
            )
            content_instruction = (
                "Format Marc's content above into the requested layout, preserving his "
                "argument and every [STAT TO VERIFY] marker exactly. You own the form, not "
                "the substance."
            )
        else:
            content_block = ""
            content_instruction = (
                "You don't have Marc's content for this theme yet (he hasn't run `/content` "
                "on it). Build the best version from the theme and note in one line that "
                "Marc's content would sharpen it. Keep substance intact; you own the form."
            )
        augmented = (
            f"The user wants a **{fmt.upper()}** for: {theme}\n\n"
            f"{audience_line}{content_block}"
            f"FORMAT SPEC: {FORMAT_SPECS[fmt]}\n\n"
            f"TPDL BRANDING (official charte): near-black #0A0A0A, accent #34D591, Funnel Sans, no AI hype.\n\n"
            f"As Oliver, produce this format. {content_instruction}"
        )
        return {
            "augmented_message": augmented,
            "action": "produced_format",
            "task_title": f"{fmt.upper()} — {theme[:50]}",
            "metadata": {"format": fmt, "theme": theme, "used_marc_content": bool(marc_content)},
        }
