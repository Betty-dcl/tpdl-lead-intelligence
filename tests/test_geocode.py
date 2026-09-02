"""app/tools/geocode.py — static city/country lookup for the map view
(Betty, 2026-09-02: "une carte géographique... un point pour chaque boîte").
Pure function, no network."""
from app.tools.geocode import geocode_location


def test_known_city_resolves():
    lat, lng = geocode_location("Barcelona, Spain")
    assert 40 < lat < 42 and 1 < lng < 3


def test_city_only_no_country():
    assert geocode_location("Zurich") is not None


def test_falls_back_to_country_capital_when_city_unknown():
    coords = geocode_location("Somewhereville, Switzerland")
    assert coords is not None
    # Bern (the Swiss capital fallback), not a fabricated exact address
    lat, lng = coords
    assert 46 < lat < 48


def test_unrecognized_location_returns_none():
    assert geocode_location("Nowhereistan") is None
    assert geocode_location(None) is None
    assert geocode_location("") is None


def test_is_case_and_accent_insensitive():
    a = geocode_location("ZÜRICH, Switzerland")
    b = geocode_location("zurich, switzerland")
    assert a == b is not None


def test_country_only_still_resolves():
    assert geocode_location("Spain") is not None
    assert geocode_location("USA") is not None
