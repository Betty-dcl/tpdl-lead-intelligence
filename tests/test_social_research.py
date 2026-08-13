"""pipeline/social_research.py — the opt-in 9th (social/video) research source.

All platform CLIs are subprocess calls (OpenCLI / yt-dlp) — never actually
invoked in tests. `_run_cli`/`_run_json` are monkeypatched, same pattern as
research.py's `_post_json` fakes.
"""
from __future__ import annotations

from datetime import date

from pipeline import social_research as sr
from pipeline.config import EngineConfig


def cfg_on() -> EngineConfig:
    cfg = EngineConfig(live=True)
    cfg.social_scan_enabled = True
    return cfg


def cfg_off() -> EngineConfig:
    return EngineConfig(live=True)  # social_scan_enabled defaults False


# ── opt-in gate: every source must no-op when the flag is off ─────────────

def test_all_sources_noop_when_disabled(monkeypatch):
    monkeypatch.setattr(sr, "_run_json", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("must not shell out when social_scan_enabled is False")))
    monkeypatch.setattr(sr, "_run_cli", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("must not shell out when social_scan_enabled is False")))
    cfg = cfg_off()
    assert sr.twitter_search(cfg, "Cantabria Labs") == []
    assert sr.reddit_search(cfg, "Cantabria Labs") == []
    assert sr.linkedin_jobs(cfg, "Cantabria Labs") == []
    assert sr.instagram_posts(cfg, "Cantabria Labs") == []
    assert sr.youtube_search(cfg, "Cantabria Labs") == []


# ── fail-open: a broken/missing CLI must yield [], never raise ────────────

def test_run_cli_missing_binary_returns_none(monkeypatch):
    import subprocess as _sp

    def boom(*a, **k):
        raise FileNotFoundError("no such file")
    monkeypatch.setattr(_sp, "run", boom)
    assert sr._run_cli(["not-a-real-binary"]) is None


def test_run_cli_timeout_returns_none(monkeypatch):
    import subprocess as _sp

    def boom(*a, **k):
        raise _sp.TimeoutExpired(cmd="x", timeout=1)
    monkeypatch.setattr(_sp, "run", boom)
    assert sr._run_cli(["opencli", "twitter", "search", "x"]) is None


def test_run_json_unparseable_returns_empty(monkeypatch):
    monkeypatch.setattr(sr, "_run_cli", lambda *a, **k: "not json{{{")
    assert sr._run_json(["opencli"]) == []


def test_run_json_opencli_error_envelope_returns_empty(monkeypatch):
    monkeypatch.setattr(sr, "_run_cli", lambda *a, **k:
                        '{"ok": false, "error": {"message": "boom"}}')
    assert sr._run_json(["opencli"]) == []


# ── noise filter: company name must literally appear ──────────────────────

def test_mentions_requires_literal_company_name():
    assert sr._mentions("Cantabria Labs", "we love Cantabria Labs skincare")
    assert not sr._mentions("Cantabria Labs", "Rocket Lab CEO interview")


# ── account matching: punctuation/space-insensitive (regression — the first
# live test against the real Instagram account failed here: literal
# `_mentions` rejected "cantabrialabs_esp" because it has no space) ─────────

def test_account_matches_ignores_spaces_and_punctuation():
    assert sr._account_matches("Cantabria Labs", "", "cantabrialabs_esp")
    assert not sr._account_matches("Cantabria Labs", "Heliocare, Endocare y más",
                                   "unrelated_handle")


# ── Twitter: parses, filters unrelated hits, keeps URL + date ─────────────

def test_twitter_search_filters_and_parses(monkeypatch):
    monkeypatch.setattr(sr, "_run_json", lambda *a, **k: [
        {"author": "someone", "text": "Cantabria Labs launches new hire push",
         "url": "https://x.com/i/status/1", "created_at": "Tue Jun 09 10:34:32 +0000 2026"},
        {"author": "other", "text": "totally unrelated tweet",
         "url": "https://x.com/i/status/2", "created_at": "Tue Jun 09 10:34:32 +0000 2026"},
    ])
    docs = sr.twitter_search(cfg_on(), "Cantabria Labs")
    assert len(docs) == 1
    assert docs[0].source == "twitter"
    assert docs[0].url == "https://x.com/i/status/1"
    assert docs[0].published == date(2026, 6, 9)


# ── Reddit: filters, joins title+body, epoch → date ────────────────────────

def test_reddit_search_filters_and_parses(monkeypatch):
    monkeypatch.setattr(sr, "_run_json", lambda *a, **k: [
        {"title": "Cantabria Labs restructuring rumours", "selftext": "heard from a friend",
         "url": "https://reddit.com/r/x/1", "created_utc": 1700000000},
        {"title": "skincare recs", "selftext": "no company mentioned here",
         "url": "https://reddit.com/r/x/2", "created_utc": 1700000000},
    ])
    docs = sr.reddit_search(cfg_on(), "Cantabria Labs")
    assert len(docs) == 1
    assert docs[0].source == "reddit"
    assert "Cantabria Labs" in docs[0].text


# ── LinkedIn jobs: fails open on the known UI-locale error, never raises ──

def test_linkedin_jobs_fails_open_on_ui_error(monkeypatch):
    monkeypatch.setattr(sr, "_run_json", lambda *a, **k: [])  # OpenCLI error ⇒ []
    assert sr.linkedin_jobs(cfg_on(), "Cantabria Labs") == []


def test_linkedin_jobs_parses_real_postings(monkeypatch):
    monkeypatch.setattr(sr, "_run_json", lambda *a, **k: [
        {"title": "Head of Digital Marketing", "location": "Madrid",
         "description": "own CRM rollout", "url": "https://linkedin.com/jobs/1"},
    ])
    docs = sr.linkedin_jobs(cfg_on(), "Cantabria Labs")
    assert len(docs) == 1
    assert docs[0].source == "linkedin_jobs"
    assert "Head of Digital Marketing" in docs[0].title


# ── Instagram: resolves the verified account, then reads its posts ────────

def test_instagram_posts_prefers_verified_account(monkeypatch):
    calls = []

    def fake_run_json(args):
        calls.append(args)
        if args[2] == "search":
            return [
                {"name": "Cantabria Labs Belarus", "username": "cantabrialabs_by",
                 "verified": "No"},
                {"name": "Cantabria Labs official", "username": "cantabrialabs_esp",
                 "verified": "Yes"},
            ]
        return [{"caption": "Cantabria Labs summer campaign", "date": "13/08/2026"}]
    monkeypatch.setattr(sr, "_run_json", fake_run_json)
    docs = sr.instagram_posts(cfg_on(), "Cantabria Labs")
    assert len(docs) == 1
    assert docs[0].source == "instagram"
    assert docs[0].url is None
    assert docs[0].published == date(2026, 8, 13)
    assert "cantabrialabs_esp" in calls[1]


def test_instagram_posts_no_matching_account_returns_empty(monkeypatch):
    monkeypatch.setattr(sr, "_run_json", lambda *a, **k: [
        {"name": "unrelated brand", "username": "someone_else", "verified": "No"},
    ])
    assert sr.instagram_posts(cfg_on(), "Cantabria Labs") == []


# ── YouTube: filters generic/unrelated search results ──────────────────────

def test_youtube_search_filters_unrelated_videos(monkeypatch):
    lines = "\n".join([
        '{"title": "Cantabria Labs investor day highlights", '
        '"description": "CEO discusses expansion", '
        '"webpage_url": "https://youtube.com/watch?v=1", "upload_date": "20260601"}',
        '{"title": "Rocket Lab CEO sits down with Jim Cramer", '
        '"description": "unrelated interview", '
        '"webpage_url": "https://youtube.com/watch?v=2"}',
    ])
    monkeypatch.setattr(sr, "_run_cli", lambda *a, **k: lines)
    docs = sr.youtube_search(cfg_on(), "Cantabria Labs")
    assert len(docs) == 1
    assert docs[0].source == "youtube"
    assert docs[0].published == date(2026, 6, 1)
