"""Marketing dashboard mocks (Phase 5): KPIs, engagement series, case studies,
website pages, outreach pipeline. All values are hand-picked to feel realistic
for a mid-sized consulting firm."""
from datetime import date, timedelta


LINKEDIN_KPIS: dict = {
    "posts_published_30d": 12,
    "impressions_30d": 184_200,
    "engagement_rate_pct": 4.7,
    "followers_delta_30d": 142,
}

# 30 daily impression counts (oldest first). Hand-picked for a realistic shape.
_IMPRESSIONS_30D: list[int] = [
    4200, 5100, 3800, 7200, 6500, 4900, 5300,
    8100, 6700, 5400, 6200, 7800, 9100, 6300,
    5500, 7400, 8800, 6900, 5200, 4800, 7100,
    9300, 8500, 6100, 5700, 8200, 9600, 7300,
    6400, 7900,
]


def engagement_series_30d() -> list[dict]:
    today = date.today()
    return [
        {
            "date": (today - timedelta(days=29 - i)).isoformat(),
            "impressions": v,
        }
        for i, v in enumerate(_IMPRESSIONS_30D)
    ]


CASE_STUDIES: list[dict] = [
    {
        "id": "cs-001",
        "title": "Helio Capital — 100-day post-MP onboarding",
        "client": "Helio Capital",
        "sector": "Private Equity",
        "date": "2026-04-12",
        "status": "published",
        "author": "oliver",
    },
    {
        "id": "cs-002",
        "title": "Northwind Bio — pre-IPO ops scale-up",
        "client": "Northwind Bio",
        "sector": "Biotech",
        "date": "2026-03-20",
        "status": "draft",
        "author": "oliver",
    },
    {
        "id": "cs-003",
        "title": "Aurelia Foods — post-merger integration playbook",
        "client": "Aurelia Foods",
        "sector": "Consumer Goods",
        "date": "2026-02-08",
        "status": "published",
        "author": "oliver",
    },
    {
        "id": "cs-004",
        "title": "Saphire Insurance — carve-out 90-day plan",
        "client": "Saphire Insurance",
        "sector": "Financial Services",
        "date": "2026-01-22",
        "status": "published",
        "author": "oliver",
    },
]


WEBSITE_PAGES: list[dict] = [
    {"path": "/", "title": "Home", "status": "live", "seo_score": 82, "last_updated": "2026-05-10"},
    {"path": "/about", "title": "About", "status": "live", "seo_score": 74, "last_updated": "2026-04-28"},
    {"path": "/services", "title": "Services", "status": "live", "seo_score": 79, "last_updated": "2026-05-02"},
    {"path": "/case-studies", "title": "Case Studies", "status": "live", "seo_score": 88, "last_updated": "2026-05-12"},
    {"path": "/pricing", "title": "Pricing", "status": "draft", "seo_score": 51, "last_updated": "2026-05-20"},
    {"path": "/services/pe-100-day", "title": "PE 100-Day Programme", "status": "planned", "seo_score": 0, "last_updated": None},
    {"path": "/blog/ai-due-diligence", "title": "AI in Due Diligence", "status": "draft", "seo_score": 63, "last_updated": "2026-05-23"},
]


OUTREACH_PIPELINE: list[dict] = [
    {"id": "em-001", "company": "Helio Capital", "subject": "100-day plan — quick read", "status": "draft",   "author": "tom", "created_at": "2026-05-22"},
    {"id": "em-002", "company": "Northwind Bio", "subject": "Pre-IPO ops sanity-check", "status": "sent",    "author": "tom", "created_at": "2026-05-20"},
    {"id": "em-003", "company": "Boreal Logistics", "subject": "DHL playbook — same trap?", "status": "replied", "author": "tom", "created_at": "2026-05-18"},
    {"id": "em-004", "company": "Verdant Energy", "subject": "New CFO — 100-day frame", "status": "draft",  "author": "tom", "created_at": "2026-05-19"},
    {"id": "em-005", "company": "Hexa Defense", "subject": "EUR 150M ramp — staffing math",  "status": "sent",   "author": "tom", "created_at": "2026-05-25"},
    {"id": "em-006", "company": "Aurelia Foods", "subject": "Integration: 30-day mark",      "status": "sent",   "author": "tom", "created_at": "2026-05-14"},
]


ICP_TEMPLATES: list[dict] = [
    {
        "id": "tpl-pe",
        "segment": "Private Equity",
        "preview": "Mid-market PE firms post leadership change — 100-day plan offer with 2 proof points from prior portcos.",
    },
    {
        "id": "tpl-biotech",
        "segment": "Biotech",
        "preview": "Series B/C-stage biotech with IPO horizon — pre-IPO operational readiness deep-dive (2 weeks).",
    },
    {
        "id": "tpl-tech",
        "segment": "Tech / SaaS",
        "preview": "Series B → C scale-up — go-to-market & ops scaling, framed as a 6-week diagnostic.",
    },
    {
        "id": "tpl-consumer",
        "segment": "Consumer Goods",
        "preview": "Post-M&A consumer goods — integration playbook with a focus on supply chain reconciliation.",
    },
]
