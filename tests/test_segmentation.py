from app.tools.segmentation import (
    classify_function,
    classify_seniority,
    initial_crm_segment,
)


def test_function_data_beats_generic():
    assert classify_function("Chief Data Officer") == "data"
    assert classify_function("Head of Analytics") == "data"


def test_function_digital():
    assert classify_function("Chief Digital Officer") == "digital"
    assert classify_function("CTO") == "digital"
    assert classify_function("VP of Digital Transformation") == "digital"


def test_function_commercial():
    assert classify_function("VP Sales") == "commercial"
    assert classify_function("Chief Commercial Officer") == "commercial"
    assert classify_function("CEO") == "commercial"


def test_function_none_when_unclear():
    assert classify_function("Office Manager") is None
    assert classify_function(None) is None
    assert classify_function("") is None


def test_seniority_c_level_wins_over_director():
    assert classify_seniority("Managing Director") == "c_level"
    assert classify_seniority("CEO") == "c_level"
    assert classify_seniority("Chief Data Officer") == "c_level"


def test_seniority_vp_and_director_and_other():
    assert classify_seniority("VP Sales") == "vp"
    assert classify_seniority("Head of Digital") == "vp"
    assert classify_seniority("Commercial Director") == "director"
    assert classify_seniority("Analyst") == "other"
    assert classify_seniority(None) is None


def test_crm_segment_active_for_good_fit():
    assert initial_crm_segment(True, "commercial", "c_level") == 2
    assert initial_crm_segment(True, "digital", "vp") == 2
    assert initial_crm_segment(True, "data", "director") == 2


def test_crm_segment_nurture_otherwise():
    assert initial_crm_segment(False, "commercial", "c_level") == 3   # not eligible
    assert initial_crm_segment(True, None, "c_level") == 3            # no function
    assert initial_crm_segment(True, "commercial", "other") == 3      # junior


def test_crm_segment_never_returns_one():
    for elig in (True, False):
        for fn in (None, "commercial", "data", "digital"):
            for sen in (None, "c_level", "vp", "director", "other"):
                assert initial_crm_segment(elig, fn, sen) in (2, 3)


def test_function_medical_affairs():
    """Medical Affairs is a named ICP target family (Nathalie §3b) → its own bucket,
    ahead of digital/commercial (a 'Head of HCP Engagement' is med-affairs, not digital)."""
    from app.tools.segmentation import classify_function
    assert classify_function("VP Medical Affairs") == "medical_affairs"
    assert classify_function("Head of Medical Education") == "medical_affairs"
    assert classify_function("Medical Science Liaison") == "medical_affairs"
    assert classify_function("Head of HCP Engagement") == "medical_affairs"
    # a plain commercial/digital title is unaffected
    assert classify_function("VP Sales") == "commercial"
    assert classify_function("Chief Digital Officer") == "digital"


def test_apollo_icp_targeting_and_seniority_floor():
    """The Apollo query carries Nathalie's 4-function ICP baseline + a Director+
    seniority floor, so a pull is never C-suite-only and never junior noise."""
    from app.tools.apollo import ICP_BASELINE_TITLES, SENIORITY_FLOOR
    joined = " · ".join(ICP_BASELINE_TITLES).lower()
    for fam in ("commercial operations", "medical affairs", "head of crm", "omnichannel"):
        assert fam in joined
    assert "director" in SENIORITY_FLOOR and "vp" in SENIORITY_FLOOR
    assert "manager" not in SENIORITY_FLOOR and "entry" not in SENIORITY_FLOOR
