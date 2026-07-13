"""TPDL Lead Intelligence Pipeline — scored companies (mock data for V1).

The first 5 entries are real output from the Phase 1 validation run on the
Dental sector, copied verbatim from the TPDL Pipeline Documentation PDF
(Appendix B). The remaining 15 are realistic mocks across the three TPDL
sectors (Dental, Diagnostics, Dermatology). Field shape mirrors the 38-column
scored_results.csv described in PDF Section 7.

Numeric scoring (PDF Section 6):
    assessed_score = average of computed scores across signals_found
    score per signal = signal_strength (0-6) + recency (0-2) + corroboration (0-2)
"""
import random
from typing import Optional


# All 6 TPDL signal types — verbatim from PDF Section 5.
SIGNAL_TYPES = [
    "leadership_change",
    "hiring",
    "ma_expansion",
    "pe_event",
    "digital_initiative",
    "org_restructuring",
]

# TPDL service-area mapping (PDF Section 5 + Section 15 reasoning chains).
TPDL_SERVICE_AREAS = [
    "CRM and data strategy",
    "Digital execution and activation",
    "Operating model alignment",
    "Customer journey optimisation",
    "Commercial effectiveness",
]


MOCK_COMPANIES: list[dict] = [
    # ============================================================
    # 1-5: REAL DATA from PDF Appendix B (5-company test run)
    # ============================================================
    {
        "name": "Dentsply Sirona",
        "sector": "Dental",
        "country": "USA / Germany",
        "revenue": "$3.8B",
        "website": "dentsplysirona.com",
        "assessed_score": 6.5,
        "coverage": "2 of 6",
        "outreach_eligible": False,
        "icp_flag": False,
        "review_flag": False,
        "tech_stack": {
            "crm": "Salesforce",
            "marketing_automation": "none detected",
            "analytics": "Google Analytics 4",
        },
        "intelligence_summary": (
            "Dentsply Sirona is executing a declared 24-month 'Return to Growth' action plan announced "
            "in its Q4 2025 results, underpinned by restructuring efforts anchored on five pillars including "
            "customer-centricity and performance, while simultaneously appointing a new Group VP for Americas "
            "Commercial and three new Board members. Leadership change and org restructuring signals are both "
            "evidenced and corroborated; no signals were found for hiring, M&A, PE events, or digital "
            "initiatives, though the absence of marketing automation — despite Salesforce CRM being present — "
            "is a notable infrastructure gap for a company with a declared customer-centricity pillar. The "
            "combination of a live turnaround mandate, a new Americas commercial leader still within their "
            "onboarding window, and a stated customer-centricity pillar makes this a strong near-term "
            "engagement window for TPDL."
        ),
        "signals_not_evidenced": ["hiring", "ma_expansion", "pe_event", "digital_initiative"],
        "signals": [
            {
                "category": "leadership_change",
                "confidence": "high",
                "signal_strength": 5,
                "recency": 1,
                "corroboration": 2,
                "score": 8,
                "date": "2026-01-28",
                "what_happened": "Dentsply Sirona Appoints Mark R. Bezjak as Group Vice President, Americas Regional Commercial Organization, effective Jan. 28, 2026.",
                "why_it_matters": "A new regional commercial VP will audit inherited go-to-market capabilities across the Americas within 90 days, often surfacing CRM and execution gaps.",
                "tpdl_relevance": "CRM and data strategy",
                "sources": [
                    "https://globenewswire.com/news-release/2026/01/12/3216983/0/en/Dentsply-Sirona-Appoints-Mark-R-Bezjak-as-Group-Vice-President-Americas-Regional-Commercial-Organization.html",
                    "https://www.oralhealthgroup.com/dental-industry/dentsply-sirona-appoints-group-vice-president-to-drive-growth-across-the-americas-1003992925/",
                ],
            },
            {
                "category": "leadership_change",
                "confidence": "medium",
                "signal_strength": 4,
                "recency": 1,
                "corroboration": 1,
                "score": 6,
                "date": "2026-02-26",
                "what_happened": "Dentsply Sirona appointed three new members to the Board of Directors, including James Forbes, former Vice Chairman Investment Bank of Morgan.",
                "why_it_matters": "Multiple board-level appointments signal governance reset tied to the Return to Growth strategy and increased scrutiny of commercial performance.",
                "tpdl_relevance": "Commercial effectiveness",
                "sources": [
                    "https://www.globenewswire.com/news-release/2026/02/26/3246054/0/en/dentsply-sirona-reports-fourth-quarter-and-full-year-2025-results-provides-full-year-2026-outlook.html",
                ],
            },
            {
                "category": "org_restructuring",
                "confidence": "high",
                "signal_strength": 5,
                "recency": 1,
                "corroboration": 2,
                "score": 8,
                "date": "2026-02-26",
                "what_happened": "Dentsply Sirona initiated a 24-month 'Return to Growth' action plan anchored on customer-centricity, innovation, and performance.",
                "why_it_matters": "A named 24-month turnaround plan with customer-centricity as a stated pillar signals fundamental operating model and commercial process redesign at enterprise scale.",
                "tpdl_relevance": "Operating model alignment",
                "sources": [
                    "https://finance.yahoo.com/m/5b09055e-66c0-3b73-95af-2e3f7f54c1ba/dentsply-sirona-inc.-q4-2025.html",
                    "https://huangshandental.com/dentsply-sirona-launches-restructuring-plan-8-notes/",
                ],
            },
        ],
        "historical_context": "In November 2025, Dentsply Sirona named Michael Pomeroy as Interim CFO, indicating CFO-level instability in the period leading up to the Q4 2025 results and the Return to Growth announcement.",
    },
    {
        "name": "Nobel Biocare",
        "sector": "Dental",
        "country": "Switzerland",
        "revenue": "$1.2B",
        "website": "nobelbiocare.com",
        "assessed_score": 6.0,
        "coverage": "2 of 6",
        "outreach_eligible": False,
        "icp_flag": False,
        "review_flag": False,
        "tech_stack": {
            "crm": "none detected",
            "marketing_automation": "none detected",
            "analytics": "none detected",
        },
        "intelligence_summary": (
            "Nobel Biocare is actively expanding its portfolio and digital capabilities, having acquired "
            "US-based Versah and integrated the DEXIS Imprevo intra-oral scanner into its digital ecosystem, "
            "both in February 2026. Two signal types were evidenced — M&A expansion and a digital initiative — "
            "while leadership change, hiring, PE events, and org restructuring were not found; the absence of "
            "CRM, marketing automation, and analytics in the tech stack is notable given the scale of these "
            "commercial moves. Both signals fall outside the 90-day window, reducing recency points, but "
            "post-acquisition integration need and digital build-out together make Nobel Biocare a credible "
            "near-term engagement target."
        ),
        "signals_not_evidenced": ["leadership_change", "hiring", "pe_event", "org_restructuring"],
        "signals": [
            {
                "category": "ma_expansion",
                "confidence": "medium",
                "signal_strength": 4,
                "recency": 1,
                "corroboration": 1,
                "score": 6,
                "date": "2026-02-15",
                "what_happened": "Nobel Biocare acquired US-based Versah, a dental osteotomy and bone densification solutions company (February 2026).",
                "why_it_matters": "Acquisitions create duplicate systems, inconsistent processes, and misaligned commercial teams requiring integration across go-to-market functions.",
                "tpdl_relevance": "Operating model alignment",
                "sources": [
                    "https://www.investorsinhealthcare.com/articles/category/news/switzerland-nobel-biocare-expands-regeneratives-and-implant-solutions-portfolio-with-acquisition-of-versah/",
                    "perplexity (no url — financial press synthesis)",
                ],
            },
            {
                "category": "digital_initiative",
                "confidence": "medium",
                "signal_strength": 4,
                "recency": 1,
                "corroboration": 1,
                "score": 6,
                "date": "2026-02-10",
                "what_happened": "Nobel Biocare integrated the DEXIS Imprevo intra-oral scanner into its digital portfolio, strengthening end-to-end digital workflows (February 2026).",
                "why_it_matters": "Expanding the digital ecosystem signals intent to deepen customer-facing digital capabilities, which typically requires coherent customer journey design and activation.",
                "tpdl_relevance": "Digital execution and activation",
                "sources": [
                    "https://www.dental-tribune.com/c/nobel-biocare-services-ag/news/nobel-biocare-expands-digital-ecosystem-with-dexis-imprevo/",
                ],
            },
        ],
        "historical_context": "Stefan Nilsson holds the position of President at Nobel Biocare as of November 2025 — noted as historical context, not scored as an active signal.",
    },
    {
        "name": "BioHorizons (incl. Camlog)",
        "sector": "Dental",
        "country": "USA / Germany",
        "revenue": "$250M",
        "website": "biohorizons.com",
        "assessed_score": 0.0,
        "coverage": "0 of 6",
        "outreach_eligible": False,
        "icp_flag": False,
        "review_flag": True,
        "review_flag_reason": "Tech scan blocked — manual verification recommended",
        "tech_stack": {
            "crm": "blocked",
            "marketing_automation": "blocked",
            "analytics": "blocked",
        },
        "intelligence_summary": (
            "No commercial signals found in the public record over the last 6 months. Tech stack could not be "
            "verified — site blocked Wappalyzer scan. Recommend manual verification of CRM and digital "
            "infrastructure before engagement."
        ),
        "signals_not_evidenced": SIGNAL_TYPES,
        "signals": [],
    },
    {
        "name": "Anthogyr (Straumann subsidiary)",
        "sector": "Dental",
        "country": "France",
        "revenue": "$120M",
        "website": "anthogyr.com",
        "assessed_score": 0.0,
        "coverage": "0 of 6",
        "outreach_eligible": False,
        "icp_flag": False,
        "review_flag": False,
        "tech_stack": {
            "crm": "blocked",
            "marketing_automation": "blocked",
            "analytics": "blocked",
        },
        "intelligence_summary": (
            "Anthogyr is a long-established French dental subsidiary of Straumann Group, active across "
            "endodontic and implant product lines, with no recent commercial events detected in the evidence "
            "block. No buying signals were found across any of the six tracked categories, and the tech stack "
            "scan was blocked; any signals relevant to Anthogyr's commercial operations may sit at the "
            "Straumann Group parent level. Engagement with Anthogyr directly is not recommended at this time "
            "— TPDL should monitor Straumann Group and revisit Anthogyr if subsidiary-level leadership "
            "changes or digital build-out activity emerges."
        ),
        "signals_not_evidenced": SIGNAL_TYPES,
        "signals": [],
    },
    {
        "name": "TBR Dental Group",
        "sector": "Dental",
        "country": "France",
        "revenue": "$45M",
        "website": "tbr.dental",
        "assessed_score": 0.0,
        "coverage": "0 of 6",
        "outreach_eligible": False,
        "icp_flag": True,
        "review_flag": False,
        "tech_stack": {
            "crm": "none detected",
            "marketing_automation": "none detected",
            "analytics": "Google Analytics 4",
        },
        "intelligence_summary": (
            "TBR Dental Group recently achieved CE marking under EU MDR 2017/745 for all its implants — a "
            "significant regulatory milestone excluded from scoring per signal classification rules. No "
            "leadership changes, hiring activity, M&A, PE events, org restructuring, or digital initiatives "
            "were found; the tech stack shows no CRM or marketing automation, only Google Analytics 4. The "
            "absence of CRM and marketing automation is a standing structural gap, but without a triggering "
            "commercial event to create urgency, engagement timing is not compelling now — revisit if a "
            "leadership change, investment event, or expansion announcement surfaces."
        ),
        "signals_not_evidenced": SIGNAL_TYPES,
        "signals": [],
    },

    # ============================================================
    # 6-20: Realistic mocks across the 3 TPDL sectors
    # ============================================================
    {
        "name": "Straumann Group",
        "sector": "Dental",
        "country": "Switzerland",
        "revenue": "$2.4B",
        "website": "straumann.com",
        "assessed_score": 8.5,
        "coverage": "3 of 6",
        "outreach_eligible": True,
        "icp_flag": False,
        "review_flag": False,
        "tech_stack": {"crm": "Salesforce", "marketing_automation": "Marketo", "analytics": "Adobe Analytics"},
        "intelligence_summary": (
            "Straumann Group announced a major restructuring of its EMEA commercial organisation in April "
            "2026, combining direct sales markets under a single regional president and appointing a new "
            "VP Digital Solutions to lead its DSO (Dental Service Organization) push. Three signal types "
            "are evidenced — leadership change, org restructuring and a digital initiative — all within the "
            "last 90 days and double-sourced. The stated DSO commercial model shift and concurrent leadership "
            "renewal make Straumann a priority engagement window for TPDL across customer journey and "
            "operating model alignment."
        ),
        "signals_not_evidenced": ["hiring", "ma_expansion", "pe_event"],
        "signals": [
            {
                "category": "org_restructuring",
                "confidence": "high",
                "signal_strength": 5, "recency": 2, "corroboration": 2, "score": 9,
                "date": "2026-04-22",
                "what_happened": "Straumann consolidated 12 EMEA direct-sales markets under a single Regional President structure (April 2026).",
                "why_it_matters": "Region-wide operating model change creates a 6-12 month window where new harmonised commercial processes are being defined.",
                "tpdl_relevance": "Operating model alignment",
                "sources": ["https://www.dental-tribune.com/straumann-emea-restructure", "https://finance.yahoo.com/m/straumann-q1-restructure"],
            },
            {
                "category": "leadership_change",
                "confidence": "high",
                "signal_strength": 5, "recency": 2, "corroboration": 2, "score": 9,
                "date": "2026-04-15",
                "what_happened": "Straumann appointed Elena Vrbinc as VP Digital Solutions, formerly with Henry Schein Digital.",
                "why_it_matters": "A net-new VP role for Digital Solutions confirms a strategic investment in DSO-facing digital capability.",
                "tpdl_relevance": "Digital execution and activation",
                "sources": ["https://www.businesswire.com/straumann-vp-digital", "https://www.linkedin.com/posts/straumann-vrbinc"],
            },
            {
                "category": "digital_initiative",
                "confidence": "medium",
                "signal_strength": 4, "recency": 2, "corroboration": 2, "score": 8,
                "date": "2026-03-30",
                "what_happened": "Straumann announced rollout of a unified DSO customer portal across EMEA, replacing 4 legacy systems.",
                "why_it_matters": "Multi-system consolidation behind a single customer portal is a textbook customer journey + CRM integration scope.",
                "tpdl_relevance": "Customer journey optimisation",
                "sources": ["https://www.straumann.com/group/en/dso-portal", "https://www.dental-economics.com/straumann-dso-portal"],
            },
        ],
    },
    {
        "name": "Roche Diagnostics",
        "sector": "Diagnostics",
        "country": "Switzerland",
        "revenue": "$14.2B",
        "website": "diagnostics.roche.com",
        "assessed_score": 7.0,
        "coverage": "2 of 6",
        "outreach_eligible": False,
        "icp_flag": False,
        "review_flag": False,
        "tech_stack": {"crm": "Salesforce Health Cloud", "marketing_automation": "Salesforce Marketing Cloud", "analytics": "Adobe Analytics"},
        "intelligence_summary": (
            "Roche Diagnostics is hiring aggressively for digital and CRM transformation roles across its "
            "EMEA hub in Mannheim, with 14 commercial digital postings open in March-April 2026. A parallel "
            "PE-backed JV with a Spanish diagnostics distributor was announced in February. Two signals "
            "evidenced; no leadership change or org restructuring in the public record. Hiring scale and JV "
            "integration both point to active commercial transformation underway."
        ),
        "signals_not_evidenced": ["leadership_change", "ma_expansion", "digital_initiative", "org_restructuring"],
        "signals": [
            {
                "category": "hiring",
                "confidence": "high",
                "signal_strength": 4, "recency": 2, "corroboration": 2, "score": 8,
                "date": "2026-04-10",
                "what_happened": "14 active job postings for Commercial Digital, CRM and Customer Data roles across Mannheim and Basel hubs.",
                "why_it_matters": "Hiring at this scale for digital/CRM roles indicates a transformation programme already underway and a near-term need for delivery capacity.",
                "tpdl_relevance": "Digital execution and activation",
                "sources": ["https://careers.roche.com/global/en/search-results?keywords=CRM", "https://careers.roche.com/global/en/search-results?keywords=Digital"],
            },
            {
                "category": "pe_event",
                "confidence": "medium",
                "signal_strength": 3, "recency": 2, "corroboration": 1, "score": 6,
                "date": "2026-02-18",
                "what_happened": "Roche Diagnostics and a Cinven-backed Spanish distributor announced a commercial joint venture for IVD distribution in Iberia.",
                "why_it_matters": "PE-backed JV introduces governance and reporting pressure on integrated commercial performance — typical TPDL engagement context.",
                "tpdl_relevance": "Commercial effectiveness",
                "sources": ["https://www.reuters.com/business/healthcare/roche-cinven-jv"],
            },
        ],
    },
    {
        "name": "Sonova Medical",
        "sector": "Diagnostics",
        "country": "Switzerland",
        "revenue": "$3.9B",
        "website": "sonova.com",
        "assessed_score": 5.5,
        "coverage": "2 of 6",
        "outreach_eligible": False,
        "icp_flag": False,
        "review_flag": False,
        "tech_stack": {"crm": "Microsoft Dynamics", "marketing_automation": "HubSpot", "analytics": "Google Analytics 4"},
        "intelligence_summary": (
            "Sonova Medical appointed a new Chief Commercial Officer in March 2026 and disclosed a £80M "
            "infrastructure programme for its retail audiology network. Two evidenced signals, both within "
            "the 6-month window but not within 90 days. The combination of a fresh CCO mandate and active "
            "retail digital build creates a narrow window — monitor closely; engage if CCO publicly outlines "
            "a CRM consolidation thesis."
        ),
        "signals_not_evidenced": ["hiring", "ma_expansion", "pe_event", "org_restructuring"],
        "signals": [
            {
                "category": "leadership_change",
                "confidence": "medium",
                "signal_strength": 4, "recency": 1, "corroboration": 1, "score": 6,
                "date": "2026-03-04",
                "what_happened": "Sonova appointed Jacques Sauvé as Group Chief Commercial Officer, effective March 2026.",
                "why_it_matters": "A new CCO at group level typically initiates a 100-day audit of commercial and CRM capability across markets.",
                "tpdl_relevance": "CRM and data strategy",
                "sources": ["https://www.sonova.com/en/news/sauve-cco-appointment"],
            },
            {
                "category": "digital_initiative",
                "confidence": "medium",
                "signal_strength": 3, "recency": 1, "corroboration": 1, "score": 5,
                "date": "2026-02-28",
                "what_happened": "Sonova disclosed a £80M three-year retail digital infrastructure programme including unified booking and customer data platform.",
                "why_it_matters": "Multi-year digital programme at scale usually requires external partners to bridge in-house delivery gaps.",
                "tpdl_relevance": "Digital execution and activation",
                "sources": ["https://www.audiology-worldnews.com/sonova-digital-retail"],
            },
        ],
    },
    {
        "name": "Galderma",
        "sector": "Dermatology",
        "country": "Switzerland",
        "revenue": "$4.1B",
        "website": "galderma.com",
        "assessed_score": 8.0,
        "coverage": "3 of 6",
        "outreach_eligible": True,
        "icp_flag": False,
        "review_flag": False,
        "tech_stack": {"crm": "Veeva CRM", "marketing_automation": "Veeva Vault", "analytics": "Tableau"},
        "intelligence_summary": (
            "Galderma post-IPO is in active commercial transformation mode: a new VP HCP Digital announced "
            "in May 2026, a recent acquisition of an aesthetic clinic chain in DACH, and reorganised regional "
            "structures for derm vs aesthetic. Three signals evidenced, all within 90 days, double-sourced. "
            "Engage now — post-IPO scrutiny, integration complexity and a fresh HCP Digital owner align "
            "across all five TPDL service areas."
        ),
        "signals_not_evidenced": ["hiring", "pe_event", "digital_initiative"],
        "signals": [
            {
                "category": "leadership_change",
                "confidence": "high",
                "signal_strength": 5, "recency": 2, "corroboration": 2, "score": 9,
                "date": "2026-05-03",
                "what_happened": "Galderma appointed Sophie Henrard as VP HCP Digital, reporting to the Chief Commercial Officer.",
                "why_it_matters": "Net-new VP HCP Digital role indicates intent to professionalise prescriber-facing digital engagement across markets.",
                "tpdl_relevance": "Customer journey optimisation",
                "sources": ["https://www.galderma.com/news/hcp-digital-vp", "https://www.linkedin.com/posts/galderma-henrard"],
            },
            {
                "category": "ma_expansion",
                "confidence": "high",
                "signal_strength": 4, "recency": 2, "corroboration": 2, "score": 8,
                "date": "2026-04-12",
                "what_happened": "Galderma acquired DermaClinics Group, a 32-clinic DACH aesthetic network, for an undisclosed sum.",
                "why_it_matters": "Direct-to-consumer clinic network acquisition requires building B2C customer journey capability rapidly.",
                "tpdl_relevance": "Customer journey optimisation",
                "sources": ["https://www.bain.com/insights/galderma-dermaclinics", "https://www.galderma.com/news/dermaclinics-acquisition"],
            },
            {
                "category": "org_restructuring",
                "confidence": "medium",
                "signal_strength": 4, "recency": 2, "corroboration": 1, "score": 7,
                "date": "2026-03-20",
                "what_happened": "Galderma split EMEA commercial into two parallel verticals — Therapeutic Dermatology and Aesthetics — each with dedicated GM.",
                "why_it_matters": "Verticalisation creates demand for separate CRM, segmentation and operating models per vertical.",
                "tpdl_relevance": "Operating model alignment",
                "sources": ["https://www.galderma.com/news/emea-verticalisation"],
            },
        ],
    },
    {
        "name": "Cantabria Labs",
        "sector": "Dermatology",
        "country": "Spain",
        "revenue": "$420M",
        "website": "cantabrialabs.com",
        "assessed_score": 4.5,
        "coverage": "2 of 6",
        "outreach_eligible": False,
        "icp_flag": False,
        "review_flag": False,
        "tech_stack": {"crm": "none detected", "marketing_automation": "none detected", "analytics": "Google Analytics 4"},
        "intelligence_summary": (
            "Cantabria Labs hired a new Global Head of Digital Commerce in February 2026 and launched its "
            "DTC platform in two new European markets. Two signals evidenced. The absence of any CRM or "
            "marketing automation at this revenue level is itself a TPDL opportunity — the new DTC build "
            "without an underlying customer data layer will create scale issues within 12 months."
        ),
        "signals_not_evidenced": ["leadership_change", "ma_expansion", "pe_event", "org_restructuring"],
        "signals": [
            {
                "category": "hiring",
                "confidence": "medium",
                "signal_strength": 3, "recency": 1, "corroboration": 1, "score": 5,
                "date": "2026-02-08",
                "what_happened": "Cantabria Labs appointed Marta Iglesias as Global Head of Digital Commerce.",
                "why_it_matters": "A net-new Digital Commerce role + no CRM detected = capability build from scratch.",
                "tpdl_relevance": "CRM and data strategy",
                "sources": ["https://www.cantabrialabs.com/news/iglesias-digital-commerce"],
            },
            {
                "category": "digital_initiative",
                "confidence": "medium",
                "signal_strength": 3, "recency": 1, "corroboration": 1, "score": 5,
                "date": "2026-02-20",
                "what_happened": "Cantabria Labs launched DTC e-commerce in Italy and Portugal.",
                "why_it_matters": "Multi-country DTC launch without underlying CDP creates a year-12 scale ceiling.",
                "tpdl_relevance": "Digital execution and activation",
                "sources": ["https://www.cantabrialabs.com/news/dtc-italy-portugal"],
            },
        ],
    },
    {
        "name": "ISDIN",
        "sector": "Dermatology",
        "country": "Spain",
        "revenue": "$680M",
        "website": "isdin.com",
        "assessed_score": 3.0,
        "coverage": "1 of 6",
        "outreach_eligible": False,
        "icp_flag": False,
        "review_flag": False,
        "tech_stack": {"crm": "Salesforce", "marketing_automation": "Salesforce Marketing Cloud", "analytics": "Adobe Analytics"},
        "intelligence_summary": (
            "ISDIN is operationally stable in the public record with no leadership, M&A, PE or restructuring "
            "events in the last 6 months. One hiring signal flagged: a Customer Data Platform Lead posting "
            "in Barcelona — indicative of internal CDP project initiation but standalone weak signal. Monitor "
            "and revisit in Q3."
        ),
        "signals_not_evidenced": ["leadership_change", "ma_expansion", "pe_event", "digital_initiative", "org_restructuring"],
        "signals": [
            {
                "category": "hiring",
                "confidence": "low",
                "signal_strength": 2, "recency": 0, "corroboration": 1, "score": 3,
                "date": None,
                "what_happened": "Open posting for Customer Data Platform Lead, Barcelona (no posting date detected).",
                "why_it_matters": "CDP role indicates project initiation; weak as standalone without supporting signals.",
                "tpdl_relevance": "CRM and data strategy",
                "sources": ["https://careers.isdin.com/job/cdp-lead"],
            },
        ],
    },
    {
        "name": "Biofrontera AG",
        "sector": "Dermatology",
        "country": "Germany",
        "revenue": "$85M",
        "website": "biofrontera.com",
        "assessed_score": 0.0,
        "coverage": "0 of 6",
        "outreach_eligible": False,
        "icp_flag": True,
        "review_flag": False,
        "tech_stack": {"crm": "none detected", "marketing_automation": "none detected", "analytics": "Google Analytics 4"},
        "intelligence_summary": (
            "Biofrontera AG is below the €100M revenue threshold for TPDL ICP — flagged as out of scope. "
            "No commercial signals were found in the last 6 months and no tech stack was detected beyond "
            "GA4. Revisit if revenue crosses threshold or a transformative event surfaces."
        ),
        "signals_not_evidenced": SIGNAL_TYPES,
        "signals": [],
    },
    {
        "name": "Werfen",
        "sector": "Diagnostics",
        "country": "Spain",
        "revenue": "$2.1B",
        "website": "werfen.com",
        "assessed_score": 7.5,
        "coverage": "2 of 6",
        "outreach_eligible": False,
        "icp_flag": False,
        "review_flag": False,
        "tech_stack": {"crm": "Salesforce", "marketing_automation": "Pardot", "analytics": "Power BI"},
        "intelligence_summary": (
            "Werfen acquired Israeli diagnostics startup Inflammatix in March 2026 and announced a new "
            "Chief Customer Officer role in April. Both signals within 90 days, both double-sourced. The "
            "post-acquisition integration + new CCO mandate combination places Werfen in a narrow window "
            "where TPDL's operating model alignment offering directly applies."
        ),
        "signals_not_evidenced": ["hiring", "pe_event", "digital_initiative", "org_restructuring"],
        "signals": [
            {
                "category": "ma_expansion",
                "confidence": "high",
                "signal_strength": 4, "recency": 2, "corroboration": 2, "score": 8,
                "date": "2026-03-22",
                "what_happened": "Werfen acquired Inflammatix, a Tel Aviv-based IVD startup focused on host response diagnostics, for $215M.",
                "why_it_matters": "Cross-border IVD acquisition with platform integration requirements creates immediate operating model integration scope.",
                "tpdl_relevance": "Operating model alignment",
                "sources": ["https://www.werfen.com/news/inflammatix-acquisition", "https://www.reuters.com/business/healthcare/werfen-inflammatix"],
            },
            {
                "category": "leadership_change",
                "confidence": "high",
                "signal_strength": 4, "recency": 2, "corroboration": 1, "score": 7,
                "date": "2026-04-05",
                "what_happened": "Werfen created and appointed its first Chief Customer Officer, Dr. Yannick Dubois.",
                "why_it_matters": "Net-new C-level CCO role created post-acquisition signals strategic investment in customer-facing transformation.",
                "tpdl_relevance": "CRM and data strategy",
                "sources": ["https://www.werfen.com/news/cco-dubois"],
            },
        ],
    },
    {
        "name": "Eurofins Genomics",
        "sector": "Diagnostics",
        "country": "Germany",
        "revenue": "$8.5B",
        "website": "eurofinsgenomics.eu",
        "assessed_score": 6.0,
        "coverage": "2 of 6",
        "outreach_eligible": False,
        "icp_flag": False,
        "review_flag": True,
        "review_flag_reason": "Single-source PE signal — verify before action",
        "tech_stack": {"crm": "Salesforce", "marketing_automation": "Marketo", "analytics": "Adobe Analytics"},
        "intelligence_summary": (
            "Eurofins Genomics is reported to be exploring a minority PE investment in its diagnostics "
            "vertical (Perplexity-only source, no URL). A digital workflow integration with a major German "
            "lab network was confirmed in April 2026. PE signal flagged for manual verification — verify "
            "before any outreach action."
        ),
        "signals_not_evidenced": ["leadership_change", "hiring", "ma_expansion", "org_restructuring"],
        "signals": [
            {
                "category": "pe_event",
                "confidence": "low",
                "signal_strength": 3, "recency": 2, "corroboration": 0, "score": 5,
                "date": "2026-04-30",
                "what_happened": "Eurofins reportedly exploring a minority PE investment in its diagnostics vertical (financial press synthesis, unverified).",
                "why_it_matters": "PE event introduces immediate commercial performance pressure if confirmed.",
                "tpdl_relevance": "Commercial effectiveness",
                "sources": ["perplexity (no url — financial press synthesis)"],
            },
            {
                "category": "digital_initiative",
                "confidence": "medium",
                "signal_strength": 4, "recency": 2, "corroboration": 1, "score": 7,
                "date": "2026-04-18",
                "what_happened": "Eurofins Genomics integrated its order-management platform with Sonic Healthcare's German lab network covering 1,200 sites.",
                "why_it_matters": "Multi-tenant platform integration at this scale signals strategic B2B digital push.",
                "tpdl_relevance": "Digital execution and activation",
                "sources": ["https://www.eurofins.com/news/sonic-integration-2026"],
            },
        ],
    },
    {
        "name": "Sectra AB",
        "sector": "Diagnostics",
        "country": "Sweden",
        "revenue": "$280M",
        "website": "sectra.com",
        "assessed_score": 4.0,
        "coverage": "1 of 6",
        "outreach_eligible": False,
        "icp_flag": False,
        "review_flag": False,
        "tech_stack": {"crm": "HubSpot", "marketing_automation": "HubSpot", "analytics": "Google Analytics 4"},
        "intelligence_summary": (
            "Sectra AB announced expansion into the French enterprise imaging market in March 2026. One "
            "signal evidenced, well-sourced but standalone. No leadership, hiring, PE or restructuring "
            "events. Monitor — French market entry could create localised commercial scaling needs in 6-12 "
            "months."
        ),
        "signals_not_evidenced": ["leadership_change", "hiring", "pe_event", "digital_initiative", "org_restructuring"],
        "signals": [
            {
                "category": "ma_expansion",
                "confidence": "medium",
                "signal_strength": 3, "recency": 1, "corroboration": 1, "score": 5,
                "date": "2026-03-12",
                "what_happened": "Sectra announced direct market entry into France for its enterprise imaging suite, opening a Paris office.",
                "why_it_matters": "New-country direct presence requires local commercial structure and processes within 12 months.",
                "tpdl_relevance": "Operating model alignment",
                "sources": ["https://www.sectra.com/news/france-entry"],
            },
        ],
    },
    {
        "name": "DiaSorin",
        "sector": "Diagnostics",
        "country": "Italy",
        "revenue": "$1.1B",
        "website": "diasorin.com",
        "assessed_score": 5.0,
        "coverage": "2 of 6",
        "outreach_eligible": False,
        "icp_flag": False,
        "review_flag": False,
        "tech_stack": {"crm": "Salesforce", "marketing_automation": "none detected", "analytics": "Tableau"},
        "intelligence_summary": (
            "DiaSorin appointed a new VP Global Commercial Operations in March 2026 and disclosed plans for "
            "a multi-region CRM consolidation. Two signals evidenced, both within 6-month window but not "
            "within 90 days. The CRM consolidation plan directly maps to TPDL CRM and data strategy — "
            "engage if the CRM RFP becomes public."
        ),
        "signals_not_evidenced": ["hiring", "ma_expansion", "pe_event", "org_restructuring"],
        "signals": [
            {
                "category": "leadership_change",
                "confidence": "medium",
                "signal_strength": 3, "recency": 1, "corroboration": 1, "score": 5,
                "date": "2026-03-01",
                "what_happened": "DiaSorin appointed Andreas Müller as VP Global Commercial Operations.",
                "why_it_matters": "VP Commercial Ops role typically owns CRM, sales enablement and process redesign.",
                "tpdl_relevance": "Commercial effectiveness",
                "sources": ["https://www.diasorin.com/news/muller-vp-commercial-ops"],
            },
            {
                "category": "digital_initiative",
                "confidence": "medium",
                "signal_strength": 3, "recency": 1, "corroboration": 1, "score": 5,
                "date": "2026-02-25",
                "what_happened": "DiaSorin disclosed a multi-region CRM consolidation programme starting Q2 2026.",
                "why_it_matters": "CRM consolidation programmes typically run 12-18 months and require external delivery support.",
                "tpdl_relevance": "CRM and data strategy",
                "sources": ["https://www.medtechdive.com/news/diasorin-crm-consolidation"],
            },
        ],
    },
    {
        "name": "L'Oréal Dermatological Beauty",
        "sector": "Dermatology",
        "country": "France",
        "revenue": "$8.2B",
        "website": "loreal.com/en/groupe/dermatological-beauty",
        "assessed_score": 8.0,
        "coverage": "2 of 6",
        "outreach_eligible": True,
        "icp_flag": False,
        "review_flag": False,
        "tech_stack": {"crm": "Salesforce", "marketing_automation": "Salesforce Marketing Cloud", "analytics": "Adobe Analytics"},
        "intelligence_summary": (
            "L'Oréal's dermatological beauty division (La Roche-Posay, Vichy, CeraVe, SkinCeuticals) is "
            "consolidating its 4 brand-level commercial stacks into a unified HCP engagement platform — "
            "announced April 2026 with a 36-month roadmap. A new SVP HCP Channel role was created in March. "
            "Both signals within 90 days, both double-sourced. Multi-brand commercial transformation = high-"
            "priority TPDL engagement window."
        ),
        "signals_not_evidenced": ["hiring", "ma_expansion", "pe_event", "org_restructuring"],
        "signals": [
            {
                "category": "digital_initiative",
                "confidence": "high",
                "signal_strength": 5, "recency": 2, "corroboration": 2, "score": 9,
                "date": "2026-04-08",
                "what_happened": "L'Oréal Dermatological Beauty announced consolidation of 4 brand-level HCP engagement systems into a unified platform, 36-month roadmap.",
                "why_it_matters": "Multi-brand commercial system consolidation is a flagship TPDL engagement context — directly maps to CRM, customer journey and operating model.",
                "tpdl_relevance": "Customer journey optimisation",
                "sources": ["https://www.loreal-finance.com/news/dermbeauty-hcp-platform", "https://www.beautypackaging.com/news/loreal-hcp-unification"],
            },
            {
                "category": "leadership_change",
                "confidence": "high",
                "signal_strength": 4, "recency": 2, "corroboration": 2, "score": 8,
                "date": "2026-03-15",
                "what_happened": "L'Oréal Dermatological Beauty created and filled a new SVP HCP Channel role, hiring Aurélie Lemaître from Pierre Fabre.",
                "why_it_matters": "Net-new SVP role at division level signals 18-month commitment to HCP channel professionalisation.",
                "tpdl_relevance": "CRM and data strategy",
                "sources": ["https://www.businessoffashion.com/news/loreal-svp-hcp", "https://www.linkedin.com/posts/lemaitre-svp-hcp"],
            },
        ],
    },
    {
        "name": "Pierre Fabre Dermo-Cosmétique",
        "sector": "Dermatology",
        "country": "France",
        "revenue": "$2.0B",
        "website": "pierre-fabre.com",
        "assessed_score": 6.0,
        "coverage": "2 of 6",
        "outreach_eligible": False,
        "icp_flag": False,
        "review_flag": False,
        "tech_stack": {"crm": "Veeva CRM", "marketing_automation": "Veeva Vault", "analytics": "Power BI"},
        "intelligence_summary": (
            "Pierre Fabre Dermo-Cosmétique launched a 200-pharmacist HCP digital advocacy programme in "
            "March 2026 and is hiring 22 digital roles across France, Spain and Italy. Two signals "
            "evidenced. The hiring + digital programme combination indicates active transformation; engage "
            "if the programme expands to D-A-CH markets."
        ),
        "signals_not_evidenced": ["leadership_change", "ma_expansion", "pe_event", "org_restructuring"],
        "signals": [
            {
                "category": "digital_initiative",
                "confidence": "medium",
                "signal_strength": 4, "recency": 1, "corroboration": 1, "score": 6,
                "date": "2026-03-18",
                "what_happened": "Pierre Fabre Dermo-Cosmétique launched 'Pharmacien Conseil 360°', a 200-pharmacist HCP digital advocacy programme in France.",
                "why_it_matters": "HCP advocacy programmes at scale require coherent customer journey orchestration and reporting.",
                "tpdl_relevance": "Customer journey optimisation",
                "sources": ["https://www.pierre-fabre.com/news/pharmacien-conseil-360"],
            },
            {
                "category": "hiring",
                "confidence": "medium",
                "signal_strength": 3, "recency": 2, "corroboration": 1, "score": 6,
                "date": "2026-04-25",
                "what_happened": "22 active digital and CRM postings across France, Spain and Italy.",
                "why_it_matters": "Hiring concentration in digital indicates a 12-month capability build window.",
                "tpdl_relevance": "Digital execution and activation",
                "sources": ["https://careers.pierre-fabre.com/digital-roles"],
            },
        ],
    },
    {
        "name": "Almirall",
        "sector": "Dermatology",
        "country": "Spain",
        "revenue": "$1.0B",
        "website": "almirall.com",
        "assessed_score": 0.0,
        "coverage": "0 of 6",
        "outreach_eligible": False,
        "icp_flag": False,
        "review_flag": False,
        "tech_stack": {"crm": "Veeva CRM", "marketing_automation": "Veeva Vault", "analytics": "Tableau"},
        "intelligence_summary": (
            "No commercial signals found in the public record over the last 6 months. Tech stack is "
            "consistent with a maturing pharma commercial operation (Veeva CRM + Vault). Monitor and "
            "revisit quarterly — if a leadership change or M&A event surfaces, engagement timing flips fast."
        ),
        "signals_not_evidenced": SIGNAL_TYPES,
        "signals": [],
    },
    {
        "name": "IBSA Institut Biochimique SA",
        "sector": "Dental",
        "country": "Switzerland",
        "revenue": "$830M",
        "website": "ibsagroup.com",
        "assessed_score": 5.0,
        "coverage": "1 of 6",
        "outreach_eligible": False,
        "icp_flag": False,
        "review_flag": False,
        "tech_stack": {"crm": "Veeva CRM", "marketing_automation": "none detected", "analytics": "Google Analytics 4"},
        "intelligence_summary": (
            "IBSA appointed a new Global Head of Customer Experience in February 2026, a previously "
            "non-existent role at the group. One signal evidenced. The customer experience focus, paired "
            "with the absence of marketing automation, signals an emerging CX transformation programme."
        ),
        "signals_not_evidenced": ["hiring", "ma_expansion", "pe_event", "digital_initiative", "org_restructuring"],
        "signals": [
            {
                "category": "leadership_change",
                "confidence": "medium",
                "signal_strength": 4, "recency": 1, "corroboration": 0, "score": 5,
                "date": "2026-02-14",
                "what_happened": "IBSA appointed Lucia Romano as Group Head of Customer Experience — newly created role.",
                "why_it_matters": "Net-new Group CX role + absent marketing automation = build-from-scratch CX programme.",
                "tpdl_relevance": "Customer journey optimisation",
                "sources": ["perplexity (no url — Italian trade press)"],
            },
        ],
    },
    {
        "name": "Laboratoires Expanscience",
        "sector": "Dermatology",
        "country": "France",
        "revenue": "$310M",
        "website": "expanscience.com",
        "assessed_score": 0.0,
        "coverage": "0 of 6",
        "outreach_eligible": False,
        "icp_flag": False,
        "review_flag": False,
        "tech_stack": {"crm": "none detected", "marketing_automation": "none detected", "analytics": "Google Analytics 4"},
        "intelligence_summary": (
            "No commercial signals found in the public record over the last 6 months. The tech stack shows "
            "no CRM or marketing automation — a structural gap at this revenue level but not paired with a "
            "triggering event. Monitor; engagement timing not compelling now."
        ),
        "signals_not_evidenced": SIGNAL_TYPES,
        "signals": [],
    },
    {
        "name": "NADMED",
        "sector": "Dental",
        "country": "Finland",
        "revenue": "$95M",
        "website": "nadmed.com",
        "assessed_score": 0.0,
        "coverage": "0 of 6",
        "outreach_eligible": False,
        "icp_flag": True,
        "review_flag": False,
        "tech_stack": {"crm": "none detected", "marketing_automation": "none detected", "analytics": "Google Analytics 4"},
        "intelligence_summary": (
            "NADMED is below the €100M revenue threshold for TPDL ICP — flagged as out of scope. No "
            "commercial signals were found and the tech stack shows no CRM. Revisit if revenue crosses "
            "threshold or a transformative event surfaces."
        ),
        "signals_not_evidenced": SIGNAL_TYPES,
        "signals": [],
    },
]


# Sector counts (matches the PDF Section 2 — but here computed from the mock list).
def sector_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    for c in MOCK_COMPANIES:
        counts[c["sector"]] = counts.get(c["sector"], 0) + 1
    return counts


def all_companies() -> list[dict]:
    return list(MOCK_COMPANIES)


def random_companies(n: int = 3, sector: Optional[str] = None) -> list[dict]:
    """Used by Sarah's /scan slash command."""
    pool = MOCK_COMPANIES
    if sector:
        sector_low = sector.lower()
        filtered = [c for c in pool if sector_low in c["sector"].lower()]
        if filtered:
            pool = filtered
    if len(pool) <= n:
        return list(pool)
    return random.sample(pool, n)


def find_company(name: str) -> Optional[dict]:
    """Used by Lea's /score and Tom's /email slash commands."""
    name_low = name.strip().lower()
    if not name_low:
        return None
    for c in MOCK_COMPANIES:
        if c["name"].lower() == name_low:
            return c
    for c in MOCK_COMPANIES:
        if name_low in c["name"].lower():
            return c
    return None
