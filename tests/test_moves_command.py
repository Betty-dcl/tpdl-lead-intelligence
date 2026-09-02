"""Inès's /moves command (executive-moves review queue) — chantier 4/4 Slice 1.
Dispatch-level tests, zero LLM calls (InesAgent.__new__ skips __init__)."""
from app.agents.ines import InesAgent
from app.database import SessionLocal
from app.models import ExecutiveMove

TEST_PERSON = "__Test Moves Person__"


def _make_agent():
    return InesAgent.__new__(InesAgent)


def _insert_move(status="new"):
    with SessionLocal() as db:
        m = ExecutiveMove(
            person_name=TEST_PERSON, new_title="Chief Medical Officer",
            new_company="__Test Moves Pharma__", quote="q", source_url="https://x",
            seniority_tier="c_level", role_function="cmo", status=status,
            dedup_key=f"movescmdtest|{status}",
        )
        db.add(m)
        db.commit()
        db.refresh(m)
        return m.id


def _cleanup():
    with SessionLocal() as db:
        db.query(ExecutiveMove).filter(ExecutiveMove.person_name == TEST_PERSON).delete()
        db.commit()


def test_moves_review_empty_then_populated():
    _cleanup()
    agent = _make_agent()
    try:
        empty = agent._dispatch_command("/moves review")
        assert empty["metadata"]["count"] == 0
        assert "No moves" in empty["augmented_message"]

        move_id = _insert_move()
        listed = agent._dispatch_command("/moves review")
        assert listed["metadata"]["count"] >= 1
        assert TEST_PERSON in listed["augmented_message"]
        assert f"#{move_id}" in listed["augmented_message"]
    finally:
        _cleanup()


def test_moves_approve_unknown_id():
    agent = _make_agent()
    out = agent._dispatch_command("/moves approve 999999999")
    assert "not found" in out["augmented_message"] or "wasn't" in out["augmented_message"]


def test_moves_approve_no_id_asks_for_one():
    agent = _make_agent()
    out = agent._dispatch_command("/moves approve")
    assert "valid id" in out["augmented_message"]


def test_moves_approve_and_dismiss_change_status():
    agent = _make_agent()
    move_id = _insert_move()
    try:
        approved = agent._dispatch_command(f"/moves approve {move_id}")
        assert "Approved" in approved["augmented_message"]
        with SessionLocal() as db:
            m = db.get(ExecutiveMove, move_id)
            assert m.status == "approved"

        # re-approving an already-approved move is a no-op that says so
        again = agent._dispatch_command(f"/moves approve {move_id}")
        assert "already" in again["augmented_message"]

        dismissed = agent._dispatch_command(f"/moves dismiss {move_id}")
        assert "Dismissed" in dismissed["augmented_message"]
        with SessionLocal() as db:
            m = db.get(ExecutiveMove, move_id)
            assert m.status == "dismissed"
            assert m.dismissed_at is not None
    finally:
        _cleanup()


def test_moves_approved_lists_approved_only():
    agent = _make_agent()
    move_id = _insert_move(status="approved")
    try:
        out = agent._dispatch_command("/moves approved")
        assert out["metadata"]["count"] >= 1
        assert f"#{move_id}" in out["augmented_message"]
    finally:
        _cleanup()


def test_moves_connected_requires_approved_first():
    agent = _make_agent()
    move_id = _insert_move(status="new")
    try:
        out = agent._dispatch_command(f"/moves connected {move_id}")
        assert "must be approved first" in out["augmented_message"]
        with SessionLocal() as db:
            assert db.get(ExecutiveMove, move_id).status == "new"
    finally:
        _cleanup()


def test_moves_full_lifecycle_to_followup():
    from datetime import date, timedelta

    agent = _make_agent()
    move_id = _insert_move(status="new")
    try:
        agent._dispatch_command(f"/moves approve {move_id}")
        connected = agent._dispatch_command(f"/moves connected {move_id}")
        assert "connected" in connected["augmented_message"].lower()
        with SessionLocal() as db:
            m = db.get(ExecutiveMove, move_id)
            assert m.status == "connection_sent"
            assert m.connection_sent_at is not None
            assert m.follow_up_date is not None
            # Not due yet (follow-up is ~4 months out) — force it into the past
            # to exercise /moves followup deterministically, no time travel needed.
            m.follow_up_date = date.today() - timedelta(days=1)
            db.commit()

        followup = agent._dispatch_command("/moves followup")
        assert followup["metadata"]["count"] >= 1
        assert f"#{move_id}" in followup["augmented_message"]

        followed_up = agent._dispatch_command(f"/moves followed-up {move_id}")
        assert "followed up" in followed_up["augmented_message"].lower()
        with SessionLocal() as db:
            m = db.get(ExecutiveMove, move_id)
            assert m.status == "follow_up_sent"
            assert m.follow_up_sent_at is not None

        # Now nothing left due
        followup_again = agent._dispatch_command("/moves followup")
        assert not any(f"#{move_id}" in line for line in
                       followup_again["augmented_message"].splitlines())
    finally:
        _cleanup()


def test_moves_followed_up_requires_connected_first():
    agent = _make_agent()
    move_id = _insert_move(status="approved")
    try:
        out = agent._dispatch_command(f"/moves followed-up {move_id}")
        assert "connected" in out["augmented_message"].lower()
        with SessionLocal() as db:
            assert db.get(ExecutiveMove, move_id).status == "approved"
    finally:
        _cleanup()
