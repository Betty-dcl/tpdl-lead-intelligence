from app.main import _is_public


def test_public_paths_allowed():
    for p in ["/", "/marketing", "/login", "/api/login", "/api/me", "/api/logout",
              "/api/agents", "/api/intel/stats", "/api/marketing",
              "/api/marketing/editions", "/static/css/app.css", "/favicon.ico",
              "/healthz"]:
        assert _is_public(p), p


def test_memory_api_is_NOT_public():
    # Regression: "/api/memory".startswith("/api/me") must not leak the brand-memory API.
    for p in ["/api/memory", "/api/memory/brand-voice", "/api/memory/feedback"]:
        assert not _is_public(p), p


def test_protected_paths_blocked():
    for p in ["/api/chat/hugo", "/api/companies", "/api/conversations",
              "/intel", "/agent/hugo", "/api/agentsfoo"]:
        assert not _is_public(p), p
