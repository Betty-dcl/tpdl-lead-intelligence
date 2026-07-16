"""Engine-trigger API: dry-run smoke test is safe (no DB writes); live never runs
inline (gated behind the API key, and deferred to the CLI so it can't hang or
spend without an explicit terminal command)."""
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

_KEY = bool(settings.anthropic_api_key) and settings.anthropic_api_key != "not-set"


def _client():
    return TestClient(app)


def test_engine_status_shape():
    with _client() as c:
        d = c.get("/api/engine/status").json()
        assert d["dry_run_available"] is True
        assert d["live_available"] is _KEY          # tracks real key presence
        assert (d["live_blocker"] is None) is _KEY
        assert "frozen" in d["reference_run"]


def test_engine_dry_run_scores_without_touching_db():
    from app.database import SessionLocal
    from app.models import Company
    with SessionLocal() as db:
        before = db.query(Company).count()
    with _client() as c:
        d = c.post("/api/engine/run", json={"live": False}).json()
        assert d["mode"] == "dry-run"
        assert d["imported"] is False and d["cost_usd"] == 0.0
        assert d["assessed_score"] > 0
        assert d["company"] == "Probe Diagnostics AG"
    with SessionLocal() as db:
        after = db.query(Company).count()
    assert after == before                          # dry-run never writes companies


def test_engine_live_never_runs_inline():
    """With a key it defers to the CLI (501); without a key it's blocked (400).
    Either way the request must NOT kick a paid run inline."""
    with _client() as c:
        r = c.post("/api/engine/run", json={"live": True})
        assert r.status_code in (400, 501)
        detail = r.json()["detail"]
        if _KEY:
            assert "CLI" in detail or "pipeline.runner" in detail
        else:
            assert "ANTHROPIC_API_KEY" in detail
