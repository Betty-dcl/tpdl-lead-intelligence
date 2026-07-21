"""Inès's radars — pure functions, no DB, no network (so they're unit-testable).

Three radars:
  1. Lunch Campaign — company/person based in Switzerland or Spain (regions where
     TPDL is physically present) → approach in person (coffee/lunch), not LinkedIn.
  2. Language — person based in Spain OR with a clearly Spanish name → communicate
     in Spanish (`es`).
  3. Premium 5 — a manual hand-pick (handled in the agent, not here).
"""
from __future__ import annotations

# Region hint tokens → ISO-ish country tag. Lowercased substring match on the
# free-text location string from Apollo / the company record.
_SWISS_HINTS = (
    "switzerland", "suisse", "schweiz", "svizzera", " ch", ",ch",
    "zurich", "zürich", "geneva", "genève", "geneve", "basel", "bern",
    "lausanne", "zug", "lugano", "winterthur",
)
_SPAIN_HINTS = (
    "spain", "españa", "espana", "spanien", "espagne",
    "madrid", "barcelona", "valencia", "sevilla", "seville", "bilbao",
    "malaga", "málaga", "zaragoza", "murcia", "palma", "vigo", "san sebastián",
)

# Modest heuristic sets for the Spanish-name radar (first names + surnames).
_ES_FIRST = {
    "jose", "josé", "juan", "carlos", "maria", "maría", "javier", "miguel",
    "antonio", "francisco", "manuel", "luis", "jorge", "alejandro", "sergio",
    "pablo", "diego", "fernando", "rafael", "alberto", "ramón", "ramon",
    "ana", "carmen", "lucía", "lucia", "marta", "elena", "rocío", "rocio",
    "pedro", "ignacio", "raúl", "raul", "andrés", "andres", "álvaro", "alvaro",
}
_ES_SURNAME = {
    "garcia", "garcía", "fernandez", "fernández", "gonzalez", "gonzález",
    "rodriguez", "rodríguez", "lopez", "lópez", "martinez", "martínez",
    "sanchez", "sánchez", "perez", "pérez", "gomez", "gómez", "ruiz", "diaz",
    "díaz", "hernandez", "hernández", "moreno", "muñoz", "munoz", "alvarez",
    "álvarez", "romero", "torres", "dominguez", "domínguez", "gil", "serrano",
    "ramos", "castro", "ortega", "rubio", "molina", "delgado", "ortiz",
}


def detect_country(location: str | None) -> str | None:
    """Map a free-text location to 'CH', 'ES', or None (unknown / other)."""
    if not location:
        return None
    low = location.lower()
    if any(h in low for h in _SWISS_HINTS):
        return "CH"
    if any(h in low for h in _SPAIN_HINTS):
        return "ES"
    return None


# Region buckets for the Sales-page location filter. Free-text location → one of
# CH / ES / USA / Middle East / Europe / APAC / Other. Substring match on the
# lowercased location. Order matters: CH and ES win first (TPDL's home markets),
# then Middle East, USA and APAC, and only what's left of the developed world
# falls into "Europe"; everything unmatched is "Other".
_MIDDLE_EAST_HINTS = (
    "uae", "united arab emirates", "dubai", "abu dhabi", "sharjah",
    "saudi", "riyadh", "jeddah", "qatar", "doha", "kuwait", "bahrain",
    "oman", "muscat", "jordan", "amman", "lebanon", "beirut",
    "israel", "tel aviv", "egypt", "cairo", "turkey", "türkiye", "istanbul",
)
_USA_HINTS = (
    "usa", "u.s.a", "united states", "u.s.", ", us", "america",
    "california", "new york", "massachusetts", "new jersey", "illinois",
    "pennsylvania", "washington", "texas", "florida", "boston", "chicago",
    "san diego", "san francisco", "seattle", "princeton", "cambridge, ma",
)
_APAC_HINTS = (
    "japan", "tokyo", "osaka", "china", "shanghai", "beijing", "hong kong",
    "korea", "seoul", "india", "mumbai", "bangalore", "delhi", "hyderabad",
    "singapore", "australia", "sydney", "melbourne", "new zealand", "auckland",
    "taiwan", "taipei", "thailand", "bangkok", "malaysia", "indonesia",
    "philippines", "vietnam", "apac", "asia",
)
_EUROPE_HINTS = (
    "germany", "deutschland", "france", "united kingdom", " uk", ",uk", "u.k",
    "england", "london", "scotland", "ireland", "dublin", "italy", "italia",
    "netherlands", "amsterdam", "belgium", "brussels", "sweden", "stockholm",
    "denmark", "copenhagen", "norway", "oslo", "finland", "helsinki",
    "austria", "vienna", "portugal", "lisbon", "poland", "warsaw", "greece",
    "athens", "cyprus", "czech", "prague", "hungary", "budapest", "luxembourg",
    "iceland", "romania", "slovakia", "slovenia", "croatia", "bulgaria",
    "estonia", "lithuania", "latvia", "europe", " eu", "/ eu", "e.u",
)

# Canonical order for the Sales-page filter dropdown.
GEO_REGION_ORDER = ["CH", "ES", "USA", "Middle East", "Europe", "APAC", "Other"]


def geo_region(location: str | None) -> str:
    """Bucket a free-text location into one of the Sales-page regions.

    Deterministic, order-sensitive substring match. Falls back to 'Other' for
    unknown / blank / non-target locations (e.g. Canada, 'NA')."""
    if not location:
        return "Other"
    low = location.lower()
    if any(h in low for h in _SWISS_HINTS):
        return "CH"
    if any(h in low for h in _SPAIN_HINTS):
        return "ES"
    if any(h in low for h in _MIDDLE_EAST_HINTS):
        return "Middle East"
    if any(h in low for h in _USA_HINTS):
        return "USA"
    if any(h in low for h in _APAC_HINTS):
        return "APAC"
    if any(h in low for h in _EUROPE_HINTS):
        return "Europe"
    return "Other"


def is_spanish_name(full_name: str | None) -> bool:
    if not full_name:
        return False
    tokens = [t.strip(",.").lower() for t in full_name.split()]
    if not tokens:
        return False
    if tokens[0] in _ES_FIRST:
        return True
    return any(t in _ES_SURNAME for t in tokens)


def apply_radars(full_name: str | None, location: str | None) -> dict:
    """Return the radar tags for a contact: {country, lunch_campaign, language}."""
    country = detect_country(location)
    lunch = country in ("CH", "ES")
    language = "es" if (country == "ES" or is_spanish_name(full_name)) else "en"
    return {"country": country, "lunch_campaign": lunch, "language": language}
