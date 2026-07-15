"""Gated-connector tests: Kaspr / Bouncer / Lemlist.

All three are dormant until their key lands in .env. These tests verify the
availability gate, offline-safe parsing, and the fail-closed contract — WITHOUT
any network (urlopen is monkeypatched). No API, no cost.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return json.dumps(self._payload).encode()


# ── Kaspr — drop-in for apollo.fetch_contacts ───────────────────────────────

def test_kaspr_not_configured(monkeypatch):
    from app.tools import kaspr
    monkeypatch.setattr(kaspr.settings, "kaspr_api_key", "")
    with pytest.raises(kaspr.KasprNotConfigured):
        kaspr.fetch_contacts("Acme")


def test_kaspr_parses_people_offline(monkeypatch):
    from app.tools import kaspr
    monkeypatch.setattr(kaspr.settings, "kaspr_api_key", "test-key")
    payload = {"people": [
        {"firstName": "Jane", "lastName": "Roe", "jobTitle": "Chief Digital Officer",
         "emails": ["jane@acme.com"], "linkedinUrl": "https://linkedin.com/in/jane",
         "city": "Zurich", "country": "Switzerland"},
        {"name": "Marc Dubois", "title": "CFO"},   # minimal record, missing fields
    ]}
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda req, timeout=30: _FakeResp(payload))
    out = kaspr.fetch_contacts("Acme", ("Chief Digital Officer", "CFO"))
    assert [p["full_name"] for p in out] == ["Jane Roe", "Marc Dubois"]
    assert out[0]["location"] == "Zurich, Switzerland"
    assert out[0]["email"] == "jane@acme.com"
    assert out[1]["email"] is None                       # missing → None, no crash
    # Contract parity with Apollo: identical dict keys.
    from app.tools import apollo
    assert set(out[0]) == set(apollo._person({"name": "x"}))


def test_kaspr_degrades_on_http_error(monkeypatch):
    from app.tools import kaspr
    monkeypatch.setattr(kaspr.settings, "kaspr_api_key", "test-key")

    def boom(req, timeout=30):
        raise urllib.error.HTTPError("url", 429, "Too Many Requests", {}, None)
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    assert kaspr.fetch_contacts("Acme") == []            # never crashes the caller


# ── Bouncer — email verification, fail-closed ───────────────────────────────

def test_bouncer_not_configured(monkeypatch):
    from app.tools import bouncer
    monkeypatch.setattr(bouncer.settings, "bouncer_api_key", "")
    with pytest.raises(bouncer.BouncerNotConfigured):
        bouncer.verify_email("a@b.com")


def test_bouncer_deliverable(monkeypatch):
    from app.tools import bouncer
    monkeypatch.setattr(bouncer.settings, "bouncer_api_key", "test-key")
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda req, timeout=30: _FakeResp({"status": "deliverable"}))
    v = bouncer.verify_email("jane@acme.com")
    assert v["status"] == "deliverable" and v["deliverable"] is True


def test_bouncer_risky_is_not_deliverable(monkeypatch):
    from app.tools import bouncer
    monkeypatch.setattr(bouncer.settings, "bouncer_api_key", "test-key")
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda req, timeout=30: _FakeResp({"status": "risky"}))
    v = bouncer.verify_email("maybe@acme.com")
    assert v["status"] == "risky" and v["deliverable"] is False


def test_bouncer_fails_closed_on_error(monkeypatch):
    from app.tools import bouncer
    monkeypatch.setattr(bouncer.settings, "bouncer_api_key", "test-key")

    def boom(req, timeout=30):
        raise urllib.error.HTTPError("url", 500, "err", {}, None)
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    v = bouncer.verify_email("jane@acme.com")
    assert v["status"] == "unknown" and v["deliverable"] is False   # fail closed


# ── Lemlist — outbound sequences, gated ─────────────────────────────────────

def test_lemlist_not_configured(monkeypatch):
    from app.tools import lemlist
    monkeypatch.setattr(lemlist.settings, "lemlist_api_key", "")
    with pytest.raises(lemlist.LemlistNotConfigured):
        lemlist.list_campaigns()
    with pytest.raises(lemlist.LemlistNotConfigured):
        lemlist.add_lead_to_campaign("cmp1", "a@b.com")


def test_lemlist_add_lead_never_fakes_success(monkeypatch):
    from app.tools import lemlist
    monkeypatch.setattr(lemlist.settings, "lemlist_api_key", "test-key")

    def boom(req, timeout=30):
        raise urllib.error.HTTPError("url", 400, "Bad Request", {}, None)
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    out = lemlist.add_lead_to_campaign("cmp1", "jane@acme.com")
    assert out["ok"] is False                            # never reports a send that failed


def test_lemlist_add_lead_ok(monkeypatch):
    from app.tools import lemlist
    monkeypatch.setattr(lemlist.settings, "lemlist_api_key", "test-key")
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda req, timeout=30: _FakeResp({"_id": "lead1"}))
    out = lemlist.add_lead_to_campaign("cmp1", "jane@acme.com", first_name="Jane")
    assert out["ok"] is True and out["email"] == "jane@acme.com"
