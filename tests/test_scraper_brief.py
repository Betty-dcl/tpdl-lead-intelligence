"""Inès's scraper-ready brief — deterministic, no invented people, §3b/§3c intact."""
from types import SimpleNamespace

from app.tools.scraper_brief import (
    MED_AFFAIRS_TITLES,
    company_brief,
    render_batch_line,
    render_company_brief,
    render_shared_config,
    salesnav_geography,
    tieback_checks,
)


def _company(**kw):
    base = dict(name="Cantabria Labs", sector_bucket="Dermatology",
                location="Madrid, Spain", assessed_score=8.5,
                s1_category="leadership_change")
    base.update(kw)
    return SimpleNamespace(**base)


def test_company_brief_structure():
    b = company_brief(_company())
    assert b["company"] == "Cantabria Labs"
    assert b["radar"]["country"] == "ES"
    assert b["radar"]["lunch_campaign"] is True
    assert b["radar"]["language"] == "es"
    # signal-driven roles, not a generic CEO/CTO/CFO pull
    assert b["priority_roles"]  # non-empty
    assert "Spain" in b["salesnav_geography"]
    assert len(b["tieback"]) == 3


def test_salesnav_geography_by_country():
    assert "Spain" in salesnav_geography("ES")
    assert "Switzerland" in salesnav_geography("CH")
    assert "HQ country" in salesnav_geography(None)


def test_tieback_names_pierre_for_spain_only():
    """§3c: Pierre is Barcelona-based → surfaced for the Spanish targets."""
    assert "Pierre is Barcelona-based" in " ".join(tieback_checks("ES"))
    assert "Pierre is Barcelona-based" not in " ".join(tieback_checks("CH"))
    # the three checks are always PipeDrive + partner + first-degree
    joined = " ".join(tieback_checks(None)).lower()
    assert "pipedrive" in joined and "partner" in joined and "first-degree" in joined


def test_render_company_brief_keeps_3b_and_3c():
    txt = render_company_brief(_company())
    # §3b: the 4 ICP functions + Medical Affairs SEPARATE
    assert "C-Suite" in txt and "Commercial & Marketing" in txt and "Digital & Technology" in txt
    assert "SEPARATE sub-batch" in txt and MED_AFFAIRS_TITLES[0] in txt
    # Sales Nav config
    assert "Sales Navigator config" in txt and "Geography" in txt
    # §3c tie-back
    assert "Tie-back check" in txt and "PipeDrive" in txt
    # recent-join capture field drives the SDR congratulate rule
    assert "recent join" in txt


def test_render_shared_config_is_company_agnostic():
    cfg = render_shared_config()
    assert "SHARED SCRAPER CONFIG" in cfg
    assert "Medical Affairs → SEPARATE SUB-BATCH" in cfg
    assert "Tie-back check" in cfg
    # no company name leaks into the shared block
    assert "Cantabria" not in cfg


def test_render_batch_line_varies_per_company():
    line = render_batch_line(_company(name="Ferrer", location="Barcelona, Spain"))
    assert "Ferrer" in line and "Barcelona" in line
    assert "prioritise:" in line and "Sales Nav geography:" in line


def test_brief_never_contains_a_fabricated_name():
    """The brief describes WHO to pull, never invents a person — no name field."""
    b = company_brief(_company())
    assert "full_name" not in b and "email" not in b and "linkedin_url" not in b
