from app.tools.segmentation import (
    classify_function,
    classify_seniority,
    flags_vp_equivalent,
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


def test_function_spanish_french_titles():
    """The campaign is Spain-focused → common ES/FR titles must classify, not fall to None."""
    assert classify_function("Director Comercial") == "commercial"     # ES
    assert classify_function("Directora de Ventas") == "commercial"    # ES
    assert classify_function("Directeur Commercial") == "commercial"   # FR
    assert classify_function("Director de Transformación Digital") == "digital"  # ES + accent
    assert classify_function("Responsable de Datos y Analítica") == "data"       # ES + accent
    assert classify_function("Director de Asuntos Médicos") == "medical_affairs" # ES + accent


def test_accents_are_folded_not_stripped():
    """'Médicos' must fold to 'medicos' (a real hint), not be mangled to 'm dicos'."""
    assert classify_function("Directora Médica") == "medical_affairs"
    assert classify_function("Président") == "commercial"


def test_seniority_director_general_is_c_level():
    """In ES/FR a 'Director General' IS the CEO — must not be demoted to 'director'."""
    assert classify_seniority("Director General") == "c_level"
    assert classify_seniority("Directora General") == "c_level"
    assert classify_seniority("Directeur Général") == "c_level"
    assert classify_seniority("Gerente General") == "c_level"
    # a plain directorship is still 'director'
    assert classify_seniority("Director Comercial") == "director"
    assert classify_seniority("Directrice Marketing") == "director"


def test_vp_equivalent_flag():
    """Senior Manager is below the floor but may be VP-equivalent at a small company → flag."""
    assert flags_vp_equivalent("Senior Manager, Commercial Operations") is True
    assert flags_vp_equivalent("Gerente Senior") is True
    # anyone already at/above the floor is not 'VP-equivalent-borderline'
    assert flags_vp_equivalent("VP Sales") is False
    assert flags_vp_equivalent("Director General") is False
    # a plain junior with no VP-equivalent signal is not flagged
    assert flags_vp_equivalent("Analyst") is False
    assert flags_vp_equivalent(None) is False


def test_apollo_icp_targeting_and_seniority_floor():
    """The Apollo query carries Nathalie's 4-function ICP baseline + a Director+
    seniority floor, so a pull is never C-suite-only and never junior noise."""
    from app.tools.apollo import ICP_BASELINE_TITLES, SENIORITY_FLOOR
    joined = " · ".join(ICP_BASELINE_TITLES).lower()
    for fam in ("commercial operations", "medical affairs", "head of crm", "omnichannel"):
        assert fam in joined
    assert "director" in SENIORITY_FLOOR and "vp" in SENIORITY_FLOOR
    assert "manager" not in SENIORITY_FLOOR and "entry" not in SENIORITY_FLOOR
