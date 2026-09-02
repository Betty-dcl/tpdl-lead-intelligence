"""Static city/country → (lat, lng) lookup — places a pin per company on the
Market Watch map (Betty, 2026-09-02: "une carte géographique... un point pour
chaque boîte, genre un pin"). Deliberately NOT a live geocoding API call: no
cost, no new dependency, no per-company network round trip, no per-request
delay. Coverage is necessarily partial (a few hundred major life-science hubs
+ capitals) — a company whose location doesn't resolve here simply gets no
pin on the map (never a fabricated/guessed position; the table/filters still
show it normally).
"""
from __future__ import annotations

import re
import unicodedata


def _norm(s: str) -> str:
    folded = unicodedata.normalize("NFKD", s.lower())
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", folded).strip()


# Major life-science/pharma hub cities + world capitals/major metros.
# (lat, lng), approximate to ~2 decimals — enough to place a map pin, not a
# survey-grade address.
_CITIES: dict[str, tuple[float, float]] = {
    # Switzerland
    "zurich": (47.37, 8.54), "basel": (47.56, 7.59), "geneva": (46.20, 6.14),
    "zug": (47.17, 8.52), "bern": (46.95, 7.45), "lausanne": (46.52, 6.63),
    "lucerne": (47.05, 8.31), "st gallen": (47.42, 9.38), "baar": (47.20, 8.53),
    # Spain
    "madrid": (40.42, -3.70), "barcelona": (41.39, 2.17), "valencia": (39.47, -0.38),
    "seville": (37.39, -5.99), "bilbao": (43.26, -2.93), "zaragoza": (41.65, -0.88),
    "san sebastian": (43.32, -1.98),
    # France
    "paris": (48.86, 2.35), "lyon": (45.76, 4.83), "toulouse": (43.60, 1.44),
    "marseille": (43.30, 5.37), "lille": (50.63, 3.06), "les ulis": (48.68, 2.17),
    "strasbourg": (48.58, 7.75), "nantes": (47.22, -1.55), "boulogne billancourt": (48.84, 2.24),
    # UK / Ireland
    "london": (51.51, -0.13), "cambridge": (52.21, 0.12), "oxford": (51.75, -1.26),
    "manchester": (53.48, -2.24), "edinburgh": (55.95, -3.19), "cardiff": (51.48, -3.18),
    "reading": (51.46, -0.97), "slough": (51.51, -0.60),
    "dublin": (53.35, -6.26), "bray": (53.20, -6.10), "cork": (51.90, -8.47),
    # Germany / Austria
    "berlin": (52.52, 13.40), "munich": (48.14, 11.58), "frankfurt": (50.11, 8.68),
    "hamburg": (53.55, 9.99), "cologne": (50.94, 6.96), "leverkusen": (51.03, 6.98),
    "darmstadt": (49.87, 8.65), "mannheim": (49.49, 8.47), "ingelheim": (49.97, 8.06),
    "biberach": (48.10, 9.79), "vienna": (48.21, 16.37),
    # Benelux / Nordics
    "amsterdam": (52.37, 4.90), "rotterdam": (51.92, 4.48), "leiden": (52.16, 4.49),
    "utrecht": (52.09, 5.12), "brussels": (50.85, 4.35), "copenhagen": (55.68, 12.57),
    "stockholm": (59.33, 18.07), "oslo": (59.91, 10.75), "helsinki": (60.17, 24.94),
    # Italy / Portugal / Eastern Europe / Greece
    "milan": (45.46, 9.19), "rome": (41.90, 12.50), "turin": (45.07, 7.69),
    "lisbon": (38.72, -9.14), "porto": (41.15, -8.61), "warsaw": (52.23, 21.01),
    "prague": (50.08, 14.44), "budapest": (47.50, 19.04), "bucharest": (44.43, 26.10),
    "athens": (37.98, 23.73),
    # Middle East
    "dubai": (25.20, 55.27), "abu dhabi": (24.45, 54.38), "doha": (25.29, 51.53),
    "riyadh": (24.71, 46.68), "tel aviv": (32.08, 34.78), "jerusalem": (31.78, 35.21),
    "jeddah": (21.54, 39.17), "manama": (26.23, 50.59), "amman": (31.95, 35.93),
    "cairo": (30.04, 31.24), "ras al khaimah": (25.79, 55.94), "sharjah": (25.35, 55.40),
    # USA / Canada
    "new york": (40.71, -74.01), "boston": (42.36, -71.06), "cambridge ma": (42.37, -71.11),
    "san francisco": (37.77, -122.42), "south san francisco": (37.66, -122.44),
    "san diego": (32.72, -117.16), "chicago": (41.88, -87.63), "philadelphia": (39.95, -75.17),
    "new jersey": (40.06, -74.41), "princeton": (40.35, -74.66), "washington": (38.91, -77.04),
    "houston": (29.76, -95.37), "atlanta": (33.75, -84.39), "fort myers": (26.64, -81.87),
    "seattle": (47.61, -122.33), "los angeles": (34.05, -118.24), "raleigh": (35.78, -78.64),
    "indianapolis": (39.77, -86.16), "minneapolis": (44.98, -93.27), "irvine": (33.68, -117.83),
    "toronto": (43.65, -79.38), "montreal": (45.50, -73.57), "vancouver": (49.28, -123.12),
    # APAC / Oceania / India
    "tokyo": (35.68, 139.69), "osaka": (34.69, 135.50), "singapore": (1.35, 103.82),
    "hong kong": (22.32, 114.17), "shanghai": (31.23, 121.47), "beijing": (39.90, 116.41),
    "seoul": (37.57, 126.98), "sydney": (-33.87, 151.21), "melbourne": (-37.81, 144.96),
    "mumbai": (19.08, 72.88), "bangalore": (12.97, 77.59), "hyderabad": (17.39, 78.49),
    "shenzhen": (22.54, 114.06), "taipei": (25.03, 121.57),
}

# Country → capital (fallback when only a bare country is given, or a city we
# don't recognize) — approximate, clearly not the company's exact address.
_COUNTRY_CAPITALS: dict[str, tuple[float, float]] = {
    "switzerland": (46.95, 7.45), "spain": (40.42, -3.70), "france": (48.86, 2.35),
    "united kingdom": (51.51, -0.13), "uk": (51.51, -0.13), "great britain": (51.51, -0.13),
    "ireland": (53.35, -6.26), "germany": (52.52, 13.40), "austria": (48.21, 16.37),
    "netherlands": (52.09, 5.10), "belgium": (50.85, 4.35), "denmark": (55.68, 12.57),
    "sweden": (59.33, 18.07), "norway": (59.91, 10.75), "finland": (60.17, 24.94),
    "italy": (41.90, 12.50), "portugal": (38.72, -9.14), "poland": (52.23, 21.01),
    "czech republic": (50.08, 14.44), "czechia": (50.08, 14.44), "hungary": (47.50, 19.04),
    "romania": (44.43, 26.10), "greece": (37.98, 23.73),
    "uae": (24.45, 54.38), "united arab emirates": (24.45, 54.38), "qatar": (25.29, 51.53),
    "saudi arabia": (24.71, 46.68), "israel": (31.78, 35.21), "jordan": (31.95, 35.93),
    "egypt": (30.04, 31.24), "bahrain": (26.23, 50.59),
    "usa": (38.91, -77.04), "united states": (38.91, -77.04), "us": (38.91, -77.04),
    "canada": (45.42, -75.70), "japan": (35.68, 139.69), "singapore": (1.35, 103.82),
    "china": (39.90, 116.41), "south korea": (37.57, 126.98), "australia": (-35.28, 149.13),
    "india": (28.61, 77.21), "taiwan": (25.03, 121.57),
}


def geocode_location(location: str | None) -> tuple[float, float] | None:
    """Best-effort, ZERO-cost lookup — no live call, no fabrication. Returns
    None (no pin) for anything not recognized in the static tables above."""
    if not location:
        return None
    parts = [p.strip() for p in location.split(",") if p.strip()]
    if not parts:
        return None
    # City usually comes first — try every segment as a city name.
    for part in parts:
        hit = _CITIES.get(_norm(part))
        if hit:
            return hit
    # Fall back to the country — usually the LAST segment.
    for part in reversed(parts):
        hit = _COUNTRY_CAPITALS.get(_norm(part))
        if hit:
            return hit
    return None
