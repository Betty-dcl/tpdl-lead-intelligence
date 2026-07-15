"""Marketing Intelligence mocks (Iris).

Iris scrapes LinkedIn + the open web for trends and news that feed Marc
(post topics and case-study angles). In V1 the scrape results are
hand-curated; V2 will wire up real LinkedIn API + news search.
"""
from typing import Optional


# ---- LinkedIn / pharma marketing trends (hand-curated) ----------------------

TRENDS: list[dict] = [
    {
        "id": "tr-001",
        "title": "HCP-facing CRM consolidation across mid-market pharma",
        "summary": "Multiple EU pharma/medtech companies (Galderma, DiaSorin, L'Oréal Dermatological Beauty) are consolidating brand-level HCP CRM stacks into unified platforms. Driver: post-COVID HCP engagement debt, multi-brand commercial fragmentation.",
        "signal_strength": 8,
        "category": "CRM & data strategy",
        "linked_companies": ["Galderma", "DiaSorin", "L'Oréal Dermatological Beauty"],
        "first_seen": "2026-04-12",
        "sources": [
            "https://www.linkedin.com/pulse/hcp-crm-consolidation-pharma-2026",
            "https://www.medtechdive.com/news/diasorin-crm-consolidation",
        ],
    },
    {
        "id": "tr-002",
        "title": "DSO commercial model shift in dental",
        "summary": "Top dental implant vendors (Straumann, Dentsply Sirona, Nobel Biocare) shifting from individual-practice sales to DSO (Dental Service Organization) chains. Requires different journey design and pricing models.",
        "signal_strength": 7,
        "category": "Customer journey optimisation",
        "linked_companies": ["Straumann Group", "Dentsply Sirona", "Nobel Biocare"],
        "first_seen": "2026-04-22",
        "sources": [
            "https://www.dental-tribune.com/dso-shift-2026",
            "https://www.linkedin.com/pulse/dso-shift-implant-market",
        ],
    },
    {
        "id": "tr-003",
        "title": "Post-IPO commercial scrutiny on dermatology brands",
        "summary": "Galderma post-IPO scrutiny driving wave of commercial reorganisations. Pattern: split into therapeutic vs aesthetic verticals, dedicated GMs, separate CRM tracks. Adjacent companies (Pierre Fabre, Almirall) likely to follow.",
        "signal_strength": 7,
        "category": "Operating model alignment",
        "linked_companies": ["Galderma", "Pierre Fabre Dermo-Cosmétique", "Almirall"],
        "first_seen": "2026-03-20",
        "sources": [
            "https://www.galderma.com/news/emea-verticalisation",
            "https://www.linkedin.com/pulse/dermatology-vertical-split-2026",
        ],
    },
    {
        "id": "tr-004",
        "title": "AI in pharma due diligence — moving from pilots to embedded",
        "summary": "PE firms running pharma deals are now expecting AI-augmented due diligence as baseline. 'AI as checklist substitute' framing is dead — buyers want hypothesis-driven AI workflows.",
        "signal_strength": 6,
        "category": "Commercial effectiveness",
        "linked_companies": [],
        "first_seen": "2026-04-05",
        "sources": [
            "https://www.bain.com/insights/ai-pharma-dd-2026",
            "https://www.linkedin.com/pulse/ai-due-diligence-checklist-dead",
        ],
    },
    {
        "id": "tr-005",
        "title": "Tech-stack 'minimum viable' floor rising for EU mid-market",
        "summary": "EU pharma/medtech companies above €100M revenue without detected CRM or marketing automation now stand out as anomalies. The 'no-tech' floor is itself a commercial signal that didn't register 18 months ago.",
        "signal_strength": 6,
        "category": "CRM & data strategy",
        "linked_companies": ["Nobel Biocare", "Cantabria Labs", "Laboratoires Expanscience"],
        "first_seen": "2026-04-28",
        "sources": [
            "https://www.linkedin.com/pulse/no-tech-floor-eu-pharma",
        ],
    },
]


# ---- News items (recent press TPDL marketing should react to) ---------------

NEWS_ITEMS: list[dict] = [
    {
        "id": "nw-001",
        "headline": "Galderma SVP HCP Channel hire — new playbook public",
        "outlet": "Business of Fashion (healthcare desk)",
        "date": "2026-05-21",
        "summary": "Galderma's new SVP HCP Channel Aurélie Lemaître published her 100-day priorities on LinkedIn. Three pillars: unified prescriber data, omnichannel patient journey, KPI-driven medical affairs.",
        "url": "https://www.businessoffashion.com/news/galderma-svp-hcp",
        "linked_company": "Galderma",
        "marketing_angle": "Topic for a Marc post: 'What Galderma's new HCP playbook reveals about the next 18 months of pharma commercial.'",
    },
    {
        "id": "nw-002",
        "headline": "Werfen's new CCO post — 'we're done buying tools, time to use them'",
        "outlet": "LinkedIn (CCO personal post)",
        "date": "2026-05-18",
        "summary": "Werfen's first-ever Chief Customer Officer Dr. Yannick Dubois posted that his Q1 focus is consolidating CRM + analytics already paid for, not new tooling. 1,200+ reactions in 48h.",
        "url": "https://www.linkedin.com/posts/dubois-werfen-cco",
        "linked_company": "Werfen",
        "marketing_angle": "Topic for a Marc post: 'The pharma stack consolidation thesis is now mainstream — what the buyer-side narrative shift means for vendors.'",
    },
    {
        "id": "nw-003",
        "headline": "Roche Diagnostics opens 14 commercial-digital roles in Mannheim",
        "outlet": "Reuters",
        "date": "2026-05-12",
        "summary": "Roche Diagnostics posted 14 senior commercial digital + CRM positions across its Mannheim and Basel hubs. Signals scale-up of an internal transformation programme.",
        "url": "https://www.reuters.com/business/healthcare/roche-diagnostics-hiring",
        "linked_company": "Roche Diagnostics",
        "marketing_angle": "Case study angle for Marc: anonymised 'building the commercial-digital function from scratch' playbook.",
    },
    {
        "id": "nw-004",
        "headline": "Dentsply Sirona Q1 2026 — Return to Growth plan on track",
        "outlet": "Yahoo Finance",
        "date": "2026-05-09",
        "summary": "Dentsply Sirona reported Q1 with explicit reference to the 24-month Return to Growth restructuring. CFO mentioned 'commercial process redesign' as on plan, customer-centricity pillar receiving investment.",
        "url": "https://finance.yahoo.com/m/dentsply-sirona-q1-2026",
        "linked_company": "Dentsply Sirona",
        "marketing_angle": "Topic for a Marc post: 'What the Dentsply Sirona Return to Growth update tells us about turnaround execution at scale in medtech.'",
    },
    {
        "id": "nw-005",
        "headline": "L'Oréal Dermatological Beauty consolidation roadmap leaked",
        "outlet": "Beauty Packaging Magazine",
        "date": "2026-05-04",
        "summary": "Details of L'Oréal Dermatological Beauty's 36-month HCP platform consolidation surfaced in trade press. Confirms scope of CRM, content and analytics unification across 4 brand silos.",
        "url": "https://www.beautypackaging.com/news/loreal-hcp-unification",
        "linked_company": "L'Oréal Dermatological Beauty",
        "marketing_angle": "Case study angle for Marc: 'Multi-brand HCP commercial consolidation — what good looks like in the first 90 days.'",
    },
    {
        "id": "nw-006",
        "headline": "Straumann EMEA restructure mentioned in CEO Q1 call",
        "outlet": "Investors call transcript",
        "date": "2026-04-25",
        "summary": "Straumann's CEO confirmed in Q1 call the new EMEA Regional President structure consolidating 12 direct-sales markets. Mentioned 'harmonised commercial KPIs' as a stated 100-day outcome.",
        "url": "https://www.straumann.com/investors/q1-2026-transcript",
        "linked_company": "Straumann Group",
        "marketing_angle": "Topic for a Marc post: 'Multi-country commercial harmonisation in medtech — the operating model debt nobody talks about.'",
    },
]


def all_trends() -> list[dict]:
    return list(TRENDS)


def all_news() -> list[dict]:
    return list(NEWS_ITEMS)


def find_trends(topic: Optional[str] = None, limit: int = 3) -> list[dict]:
    """Return top trends, optionally filtered by topic (case-insensitive substring on title/category/summary)."""
    pool = TRENDS
    if topic:
        low = topic.lower()
        filtered = [
            t for t in pool
            if low in t["title"].lower()
            or low in t["category"].lower()
            or low in t["summary"].lower()
        ]
        if filtered:
            pool = filtered
    pool = sorted(pool, key=lambda t: -t["signal_strength"])
    return pool[:limit]


def find_news(keyword: Optional[str] = None, limit: int = 3) -> list[dict]:
    """Return recent news items, optionally filtered by keyword (case-insensitive substring on headline/summary/company)."""
    pool = NEWS_ITEMS
    if keyword:
        low = keyword.lower()
        filtered = [
            n for n in pool
            if low in n["headline"].lower()
            or low in n["summary"].lower()
            or low in (n.get("linked_company") or "").lower()
        ]
        if filtered:
            pool = filtered
    pool = sorted(pool, key=lambda n: n["date"], reverse=True)
    return pool[:limit]
