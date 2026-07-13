"""LinkedIn post drafts pending validation, plus in-memory approve/reject state.

V1 only — state resets on server restart. In V2 these become tasks rows linked
to Marc's /draft_post commands and a real LinkedIn API integration.
"""
from typing import Optional

LINKEDIN_DRAFTS: list[dict] = [
    {
        "id": "draft-001",
        "topic": "AI in due diligence",
        "angle": "contrarian",
        "author": "marc",
        "created_at": "2026-05-23T09:14:00",
        "status": "pending",
        "preview": "Most firms still treat due diligence like a checklist. The ones outperforming treat it like a hypothesis test.",
        "full_text": (
            "Most firms still treat due diligence like a checklist. "
            "The ones outperforming treat it like a hypothesis test.\n\n"
            "Three shifts I've watched cut DD time by 40% — without cutting rigour:\n"
            "1) Frame the deal as a falsifiable thesis on day one\n"
            "2) Front-load the two questions that, if wrong, kill the deal\n"
            "3) Use AI to triangulate signals, not to summarise PDFs\n\n"
            "AI doesn't replace partners. It rebalances where partners spend their attention.\n\n"
            "#PrivateEquity #DueDiligence #AI"
        ),
    },
    {
        "id": "draft-002",
        "topic": "100-day plans for new C-levels",
        "angle": "data-driven",
        "author": "marc",
        "created_at": "2026-05-22T15:42:00",
        "status": "pending",
        "preview": "We looked at 30 leadership transitions in mid-market PE portcos. The pattern is brutal.",
        "full_text": (
            "We looked at 30 leadership transitions in mid-market PE portcos. The pattern is brutal.\n\n"
            "CEOs who delivered their stated 100-day plan: 11/30\n"
            "CEOs who quietly missed it: 19/30\n\n"
            "The differentiator isn't talent. It's whether the plan answers 3 questions before day 30:\n"
            "- What gets shipped this quarter?\n"
            "- What stops?\n"
            "- Who owns each item, by name?\n\n"
            "Generic transition playbooks don't survive contact with a real org chart.\n\n"
            "#Leadership #PrivateEquity"
        ),
    },
    {
        "id": "draft-003",
        "topic": "Outbound that doesn't read like outbound",
        "angle": "tactical",
        "author": "marc",
        "created_at": "2026-05-21T11:08:00",
        "status": "pending",
        "preview": "Three rules I borrowed from a friend who closes 22% of cold outbound to PE firms.",
        "full_text": (
            "Three rules I borrowed from a friend who closes 22% of cold outbound to PE firms.\n\n"
            "Rule 1: cite the signal in line one. Not a hook, a fact.\n"
            "Rule 2: the body is a hypothesis, not a pitch. \"You probably need X because of Y.\"\n"
            "Rule 3: the ask is small and specific. \"15 minutes Tuesday or Wednesday?\" beats \"a quick chat\".\n\n"
            "Most outbound fails because it tries to be friendly. The best outbound is useful first.\n\n"
            "#Outbound #Sales"
        ),
    },
    {
        "id": "draft-004",
        "topic": "Carve-outs done well",
        "angle": "case study",
        "author": "marc",
        "created_at": "2026-05-20T08:30:00",
        "status": "pending",
        "preview": "A €500M carve-out from a European industrial group — three things they got right, two they got wrong.",
        "full_text": (
            "A EUR 500M carve-out from a European industrial group — three things they got right, two they got wrong.\n\n"
            "Right:\n"
            "- TSA scope frozen at week 4, not week 12\n"
            "- IT cutover sequenced before HR (rarely done)\n"
            "- Procurement leverage preserved via a shared-services bridge\n\n"
            "Wrong:\n"
            "- Underestimated talent retention in the carved-out finance team\n"
            "- Day-1 customer comms ran 3 weeks late\n\n"
            "Carve-outs are won and lost in the first 90 days. The plan you ship on day 1 is the plan that holds.\n\n"
            "#CarveOut #PrivateEquity"
        ),
    },
    {
        "id": "draft-005",
        "topic": "The 'second 100 days' nobody plans for",
        "angle": "contrarian",
        "author": "marc",
        "created_at": "2026-05-18T17:21:00",
        "status": "pending",
        "preview": "Everyone plans the first 100 days. The second 100 days is where most plans quietly die.",
        "full_text": (
            "Everyone plans the first 100 days. The second 100 days is where most plans quietly die.\n\n"
            "Day 101-200 is when:\n"
            "- The honeymoon ends\n"
            "- The board switches from supportive to impatient\n"
            "- The org realises which changes were performative\n\n"
            "If your 100-day plan doesn't have a follow-on chapter — written before day 30 — you're flying blind into the part that actually compounds.\n\n"
            "#Leadership #Transformation"
        ),
    },
]


def list_drafts(status: Optional[str] = None) -> list[dict]:
    if status is None:
        return list(LINKEDIN_DRAFTS)
    return [d for d in LINKEDIN_DRAFTS if d["status"] == status]


def update_status(draft_id: str, new_status: str) -> Optional[dict]:
    for d in LINKEDIN_DRAFTS:
        if d["id"] == draft_id:
            d["status"] = new_status
            return d
    return None
