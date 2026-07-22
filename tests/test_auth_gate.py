from app.main import _is_public


def test_public_paths_allowed():
    # Login is the front door: only the sign-in page, auth endpoints and static
    # assets are reachable unauthenticated.
    for p in ["/login", "/api/login", "/api/me", "/api/logout",
              "/static/css/app.css", "/favicon.ico", "/healthz"]:
        assert _is_public(p), p


def test_memory_api_is_NOT_public():
    # Regression: "/api/memory".startswith("/api/me") must not leak the brand-memory API.
    for p in ["/api/memory", "/api/memory/brand-voice", "/api/memory/feedback"]:
        assert not _is_public(p), p


def test_landing_and_content_require_login():
    # The whole platform sits behind the gate now — home, marketing and the
    # data APIs that used to be public-demo are no longer reachable without login.
    for p in ["/", "/marketing", "/api/agents", "/api/intel/stats",
              "/api/marketing", "/api/marketing/editions"]:
        assert not _is_public(p), p


def test_protected_paths_blocked():
    for p in ["/api/chat/hugo", "/api/companies", "/api/conversations",
              "/intel", "/agent/hugo", "/api/agentsfoo"]:
        assert not _is_public(p), p
