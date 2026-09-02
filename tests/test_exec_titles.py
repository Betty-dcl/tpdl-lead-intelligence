"""Executive-move classifier (app/tools/exec_titles.py) — chantier 4/4 Slice 0,
2026-09-01 Nathalie meeting recap. Pure functions, no DB/network."""
from datetime import date, datetime, timezone

from app.tools.exec_titles import (
    classify_role_function,
    classify_seniority_tier,
    compute_follow_up_date,
    is_in_scope,
    purge_due,
)


def test_c_suite_named_roles_and_role_function():
    assert classify_seniority_tier("Chief Medical Officer") == "c_level"
    assert classify_role_function("Chief Medical Officer") == "cmo"
    assert classify_seniority_tier("CMO") == "c_level"
    assert classify_seniority_tier("Chief Operating Officer") == "c_level"
    assert classify_role_function("Chief Operating Officer") == "coo"
    assert classify_seniority_tier("Chief Technology Officer") == "c_level"
    assert classify_role_function("Chief Technology Officer") == "cto"
    assert classify_seniority_tier("Chief Innovation Officer") == "c_level"
    assert classify_role_function("Chief Innovation Officer") == "chief_innovation"
    assert classify_seniority_tier("Chief Information Officer") == "c_level"
    assert classify_role_function("Chief Information Officer") == "cio"


def test_c_suite_ceo_equivalent_and_multilingual():
    assert classify_seniority_tier("President") == "c_level"
    assert classify_seniority_tier("Managing Director") == "c_level"
    # ES/FR "Director General"/"Directeur Général" IS the CEO, not a mid-level director
    assert classify_seniority_tier("Director General") == "c_level"
    assert classify_seniority_tier("Directora General") == "c_level"
    assert classify_seniority_tier("Directeur Général") == "c_level"
    assert classify_seniority_tier("Gerente General") == "c_level"


def test_minus_1_svp_vp():
    assert classify_seniority_tier("Senior Vice President, Commercial") == "minus_1"
    assert classify_seniority_tier("SVP Commercial") == "minus_1"
    assert classify_seniority_tier("VP Sales") == "minus_1"
    assert classify_seniority_tier("Vicepresidente Senior") == "minus_1"


def test_minus_2_general_manager_and_senior_director():
    assert classify_seniority_tier("General Manager") == "minus_2"
    assert classify_seniority_tier("Deputy General Manager") == "minus_2"
    assert classify_seniority_tier("Senior Director, Commercial Operations") == "minus_2"
    assert classify_role_function("General Manager") == "other"  # in scope, not one of the 5 named roles


def test_bare_manager_never_matches_general_manager_hint():
    """Nathalie's own callout: 'Manager, Regulatory Affairs' must NOT match —
    a bare-substring match on 'manager' would dilute the GM filter, the
    opposite of her intent (GM should be elevated, not diluted)."""
    assert classify_seniority_tier("Manager, Regulatory Affairs") is None
    assert classify_seniority_tier("Regional Sales Manager") is None
    assert is_in_scope("Manager, Regulatory Affairs") is False


def test_out_of_scope_titles():
    # A bare "Director" (no "senior"/"general") is out of scope for THIS
    # feature (only C-suite/-1/-2 are tracked) — distinct from segmentation.py's
    # broader Director+ floor, which serves a different purpose.
    assert classify_seniority_tier("Director, Regulatory Affairs") is None
    assert classify_seniority_tier("Senior Manager") is None
    assert classify_seniority_tier("Regional Sales Rep") is None
    assert classify_seniority_tier(None) is None
    assert classify_seniority_tier("") is None


def test_is_in_scope_wrapper():
    assert is_in_scope("Chief Medical Officer") is True
    assert is_in_scope("VP Sales") is True
    assert is_in_scope("General Manager") is True
    assert is_in_scope("Director, Regulatory Affairs") is False
    assert is_in_scope(None) is False


def test_classify_role_function_no_title():
    assert classify_role_function(None) is None
    assert classify_role_function("") is None


def test_compute_follow_up_date_normal_case():
    assert compute_follow_up_date(date(2026, 1, 15)) == date(2026, 5, 15)


def test_compute_follow_up_date_month_end_clamped():
    # 31 Jan + 4 months = May has 31 days -> stays the 31st
    assert compute_follow_up_date(date(2026, 1, 31)) == date(2026, 5, 31)
    # 31 Aug + 4 months -> December has 31 days too
    assert compute_follow_up_date(date(2026, 8, 31)) == date(2026, 12, 31)
    # 31 Oct + 4 months -> February (non-leap) has 28 days -> clamped
    assert compute_follow_up_date(date(2025, 10, 31)) == date(2026, 2, 28)


def test_compute_follow_up_date_crosses_year_boundary():
    assert compute_follow_up_date(date(2026, 10, 1)) == date(2027, 2, 1)


def test_purge_due_gdpr_retention():
    today = date(2026, 9, 2)
    assert purge_due(None, today=today) is False
    just_under = datetime(2026, 6, 5, tzinfo=timezone.utc)   # 89 days before
    exactly_90 = datetime(2026, 6, 4, tzinfo=timezone.utc)   # 90 days before
    assert purge_due(just_under, today=today) is False
    assert purge_due(exactly_90, today=today) is True
    # a bare date() also works, not just datetime
    assert purge_due(date(2026, 5, 1), today=today) is True
