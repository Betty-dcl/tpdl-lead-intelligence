"""Marketing chain spine — the 5 campaign themes wire Iris → Marc → Oliver."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.tools.campaign_themes import (
    CAMPAIGN_THEMES,
    find_theme,
    render_brief,
    render_shortlist,
)


@pytest.fixture()
def client():
    with TestClient(app) as c:      # startup runs init_db + seeds agents
        yield c


def test_five_themes_each_prove_a_business_principle():
    assert len(CAMPAIGN_THEMES) == 5
    for t in CAMPAIGN_THEMES:
        assert t.business_principle and t.audience and t.angle and t.reframe
        assert t.match_terms


def test_find_theme_routes_free_text():
    assert find_theme("omnichannel is killing us").key == "omnichannel-data"
    assert find_theme("HCP engagement strategy").key == "hcp-digital"
    assert find_theme("scaling globally from Spain").key == "spanish-scale"
    assert find_theme("controlling the brand architecture").key == "architecture-brand"
    assert find_theme("mid-size commercial transformation").key == "midsize-transformation"


def test_find_theme_by_key():
    assert find_theme("spanish-scale").key == "spanish-scale"


def test_find_theme_none_when_unrelated():
    assert find_theme("quarterly tax filing deadlines") is None
    assert find_theme("") is None
    assert find_theme(None) is None


def test_render_shortlist_lists_all_five_with_principle():
    txt = render_shortlist()
    assert "Market Intel July 2026" in txt
    for t in CAMPAIGN_THEMES:
        assert t.title in txt and t.business_principle in txt


def test_render_brief_leads_with_business_principle():
    brief = render_brief(CAMPAIGN_THEMES[0])
    assert "Business principle to PROVE" in brief
    assert CAMPAIGN_THEMES[0].business_principle in brief
    assert "business problem, not IT problem" in brief


# ── wiring: Iris surfaces the spine, Marc grounds on it, Oliver knows the audience ─

def test_iris_themes_renders_campaign_spine(client):
    from app.agents import AGENT_CLASSES
    from app.database import SessionLocal
    with SessionLocal() as db:
        iris = AGENT_CLASSES["iris"].load(db, "iris")
        for cmd in ("/themes", "/campaign"):
            out = iris._dispatch_command(cmd)
            assert out["action"] == "scored_themes"
            assert "Market Intel July 2026" in out["augmented_message"]
            assert CAMPAIGN_THEMES[0].title in out["augmented_message"]
        # /trends stays a live-research command (takes a sector), not the spine
        tr = iris._dispatch_command("/trends dental")
        assert tr["metadata"]["sector"] == "dental"


def test_marc_content_injects_campaign_brief(client):
    from app.agents import AGENT_CLASSES
    from app.database import SessionLocal
    with SessionLocal() as db:
        marc = AGENT_CLASSES["marc"].load(db, "marc")
        out = marc._dispatch_command("/content omnichannel is a data problem")
        msg = out["augmented_message"]
        assert "CAMPAIGN THEME MATCH" in msg
        assert "The Hidden Cost of Fragmentation" in msg      # the principle to prove
        # a non-campaign theme gets no injected brief (but still writes content)
        plain = marc._dispatch_command("/content generic supply chain update")
        assert "CAMPAIGN THEME MATCH" not in plain["augmented_message"]
        assert plain["action"] == "wrote_content"


def test_oliver_adds_audience_for_campaign_theme(client):
    from app.agents import AGENT_CLASSES
    from app.database import SessionLocal
    with SessionLocal() as db:
        oliver = AGENT_CLASSES["oliver"].load(db, "oliver")
        out = oliver._dispatch_command("/carousel HCP engagement in the digital age")
        assert "TARGET AUDIENCE (campaign theme)" in out["augmented_message"]
        assert "Medical Affairs" in out["augmented_message"]
