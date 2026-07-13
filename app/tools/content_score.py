"""Content quality scoring — a reviewer pass over generated content.

After Marc writes a format, a reviewer call scores it 0-10 against the TPDL
brand memory (hook, data substance, audience fit, clarity, CTA) and returns a
verdict + strengths + issues. Non-blocking: scoring failure never blocks the
content itself.
"""
import json
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

REVIEWER_SYSTEM = (
    "You are TPDL's content quality reviewer. You assess drafts against the "
    "firm's brand standards with the severity of a chief editor: honest, "
    "specific, never complacent. You return STRICT JSON only — no prose, "
    "no markdown fences."
)

REVIEWER_PROMPT = """Score this {format_label} draft for The Pharma Data Lab.

{brand_voice_block}

SCORING CRITERIA (equal weight):
1. Hook strength — does the first line stop the scroll / earn the read?
2. Data substance — concrete numbers and facts, not vague claims?
3. Audience fit — speaks to C-suite/VP in pharma, medtech, dental?
4. Clarity — jargon-free, direct, active voice?
5. CTA — clear, specific next action?

DRAFT (subject: {subject}):
---
{content}
---

Return STRICT JSON only, exactly this shape:
{{"score": <number 0-10, one decimal>, "verdict": "<one honest sentence>", "strengths": ["<short>", "<short>"], "issues": ["<short>", "<short>"]}}"""


def _parse_score_json(text: str) -> Optional[dict]:
    """Extract and validate the reviewer's JSON. Returns None if unusable."""
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    # Grab the first {...} block if extra prose slipped in
    m = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    if "score" not in data:
        return None
    try:
        score = round(max(0.0, min(10.0, float(data["score"]))), 1)
    except (TypeError, ValueError):
        return None
    return {
        "score": score,
        "verdict": str(data.get("verdict", ""))[:300],
        "strengths": [str(s)[:160] for s in (data.get("strengths") or [])[:4]],
        "issues": [str(s)[:160] for s in (data.get("issues") or [])[:4]],
    }


async def score_content(content: str, format_label: str, subject: str) -> Optional[dict]:
    """Run the reviewer pass. Returns {score, verdict, strengths, issues} or None."""
    from app.agents.base import get_async_anthropic_client
    from app.config import settings
    from app.tools.memory import get_brand_voice_block

    try:
        client = get_async_anthropic_client()
        prompt = REVIEWER_PROMPT.format(
            format_label=format_label,
            brand_voice_block=get_brand_voice_block(),
            subject=subject,
            content=content[:6000],
        )
        response = await client.messages.create(
            model=settings.anthropic_model,
            system=REVIEWER_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
        )
        text = "".join(
            b.text for b in response.content if getattr(b, "type", "") == "text"
        )
        result = _parse_score_json(text)
        if result is None:
            logger.warning("[content_score] unparseable reviewer output: %.120s", text)
        return result
    except Exception as exc:
        logger.warning("[content_score] scoring failed (non-blocking): %s", exc)
        return None
