"""Maya → Inès wiring: shared shortlist definition + Inès batch hand-off."""
from app.database import SessionLocal
from app.tools.shortlist import shortlist_bands, ACT_NOW_FLOOR, MONITOR_FLOOR


def test_shortlist_bands_definition():
    with SessionLocal() as db:
        act, monitor = shortlist_bands(db)
    # ACT NOW = every in-scope company >= 8; MONITOR = 5..<8; both banded correctly
    for c in act:
        assert c.assessed_score >= ACT_NOW_FLOOR and not c.icp_flag
    for c in monitor:
        assert MONITOR_FLOOR <= c.assessed_score < ACT_NOW_FLOOR and not c.icp_flag
    # sorted by score desc
    assert all(act[i].assessed_score >= act[i+1].assessed_score for i in range(len(act)-1))


def test_ines_batch_consumes_maya_shortlist():
    from app.agents.ines import InesAgent
    from app.agents.maya import MAYA_ID  # noqa: F401 (import sanity, no cycle)
    agent = InesAgent.__new__(InesAgent)  # skip __init__ (no LLM needed for dispatch)
    out = agent._dispatch_command("/contacts shortlist")
    assert out is not None and out["action"] == "pulled_contacts"
    with SessionLocal() as db:
        act, _ = shortlist_bands(db)
    if act:
        assert "BATCH hand-off from Maya" in out["augmented_message"]
        assert out["metadata"]["act_total"] == len(act)
        # the batch names real shortlisted companies, never invents
        assert act[0].name in out["augmented_message"]
    else:
        assert "EMPTY" in out["augmented_message"]


def test_sales_pipeline_endpoint_assembles_four_stages():
    """The /pipeline view assembles all four agent stages from the scored row,
    deterministically (no LLM), and the picker comes from Maya's ACT NOW band."""
    from app.routers.intel import sales_pipeline
    with SessionLocal() as db:
        r = sales_pipeline(None, db)
        act, _ = shortlist_bands(db)
    if not act:
        assert r.get("empty") is True
        return
    assert r["company"] == act[0].name              # defaults to top ACT NOW
    assert len(r["picker"]) == min(30, len(act))
    # every stage present and reads the previous stage's real output
    assert r["hugo"]["score"] == act[0].assessed_score
    assert r["maya"]["band"] in ("ACT NOW", "MONITOR", "PARKED")
    assert r["maya"]["rank"] >= 1
    assert isinstance(r["ines"]["target_roles"], list) and r["ines"]["target_roles"]
    assert "angle" in r["julie"]
