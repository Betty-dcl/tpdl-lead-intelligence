"""Julie's /moves draft <id> — chantier 4/4 Slice 2. Dispatch-level tests,
zero LLM calls (JulieAgent.__new__ skips __init__)."""
from app.agents.julie import JulieAgent
from app.database import SessionLocal
from app.models import ExecutiveMove

TEST_PERSON = "__Test Julie Moves Person__"


def _make_agent():
    return JulieAgent.__new__(JulieAgent)


def _insert_move(**overrides):
    fields = dict(
        person_name=TEST_PERSON, new_title="Chief Medical Officer",
        new_company="__Test Julie Pharma__", previous_company="__Test Old Pharma__",
        previous_title="VP Medical Affairs", location="Zurich, Switzerland",
        quote="Acme Pharma is pleased to announce Jane Doe as its new Chief Medical Officer.",
        source_url="https://x", seniority_tier="c_level", role_function="cmo",
        status="approved", dedup_key="juliemovestest|1",
    )
    fields.update(overrides)
    with SessionLocal() as db:
        m = ExecutiveMove(**fields)
        db.add(m)
        db.commit()
        db.refresh(m)
        return m.id


def _cleanup():
    with SessionLocal() as db:
        db.query(ExecutiveMove).filter(ExecutiveMove.person_name == TEST_PERSON).delete()
        db.commit()


def test_moves_draft_no_id_asks_for_one():
    agent = _make_agent()
    out = agent._dispatch_command("/moves draft")
    assert "valid id" in out["augmented_message"]


def test_moves_draft_unknown_id():
    agent = _make_agent()
    out = agent._dispatch_command("/moves draft 999999999")
    assert "wasn't found" in out["augmented_message"]


def test_moves_draft_wrong_subcommand_redirects_to_ines():
    agent = _make_agent()
    out = agent._dispatch_command("/moves review")
    assert "Inès" in out["augmented_message"]
    assert "only handles" in out["augmented_message"]


def test_moves_draft_builds_job_switch_prompt():
    agent = _make_agent()
    move_id = _insert_move()
    try:
        out = agent._dispatch_command(f"/moves draft {move_id}")
        msg = out["augmented_message"]
        assert "Job Switch / New Role" in msg
        assert TEST_PERSON in msg
        assert "Chief Medical Officer" in msg
        assert "__Test Julie Pharma__" in msg
        assert "VP Medical Affairs" in msg   # previous role carried through
        assert "__Test Old Pharma__" in msg  # previous company carried through
        assert "PLAYBOOK" in msg             # the real andres_linkedin.md got appended
        assert out["metadata"]["move_id"] == move_id
    finally:
        _cleanup()


def test_moves_draft_flags_unapproved_move():
    agent = _make_agent()
    move_id = _insert_move(status="new", dedup_key="juliemovestest|2")
    try:
        out = agent._dispatch_command(f"/moves draft {move_id}")
        assert "not yet approved" in out["augmented_message"] or "'new'" in out["augmented_message"]
    finally:
        _cleanup()


def test_moves_draft_no_previous_role_stated():
    agent = _make_agent()
    move_id = _insert_move(previous_company=None, previous_title=None,
                           dedup_key="juliemovestest|3")
    try:
        out = agent._dispatch_command(f"/moves draft {move_id}")
        assert "no previous role stated" in out["augmented_message"]
    finally:
        _cleanup()
