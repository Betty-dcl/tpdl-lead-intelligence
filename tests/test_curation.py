"""70/30 Europe/world curation (app/tools/curation.py) — pure functions, no
DB/network. Chantier 3/4 of the 2026-09-01 Nathalie meeting recap."""
from app.tools.curation import DEFAULT_RATIO, interleave_by_tier, weekly_review_batch


def _rows(prefix: str, n: int, tier: str) -> list[dict]:
    return [{"name": f"{prefix}{i}", "market_tier": tier, "assessed_score": 10 - i}
            for i in range(n)]


def test_interleave_preserves_ratio_and_order():
    core = _rows("core", 20, "core")
    world = _rows("world", 20, "world")
    out = interleave_by_tier(core, world, DEFAULT_RATIO)
    first_ten = out[:10]
    n_core = sum(1 for c in first_ten if c["market_tier"] == "core")
    n_world = sum(1 for c in first_ten if c["market_tier"] == "world")
    assert (n_core, n_world) == (7, 3)
    # relative order within each tier is preserved
    core_order = [c["name"] for c in out if c["market_tier"] == "core"]
    world_order = [c["name"] for c in out if c["market_tier"] == "world"]
    assert core_order == [c["name"] for c in core]
    assert world_order == [c["name"] for c in world]


def test_interleave_never_drops_when_one_tier_short():
    core = _rows("core", 20, "core")
    world = _rows("world", 2, "world")
    out = interleave_by_tier(core, world, DEFAULT_RATIO)
    assert len(out) == 22   # nothing lost
    assert {c["name"] for c in out} == {c["name"] for c in core} | {c["name"] for c in world}
    # the 2 world entries appear early (proportionally due), not stranded at the end
    world_positions = [i for i, c in enumerate(out) if c["market_tier"] == "world"]
    assert max(world_positions) < len(out) - 1


def test_interleave_empty_tier_returns_the_other_unchanged():
    core = _rows("core", 5, "core")
    assert interleave_by_tier(core, []) == core
    world = _rows("world", 5, "world")
    assert interleave_by_tier([], world) == world


def test_weekly_review_batch_respects_market_tier_and_n():
    companies = _rows("core", 20, "core") + _rows("world", 20, "world")
    batch = weekly_review_batch(companies, n=10)
    assert len(batch) == 10
    assert sum(1 for c in batch if c["market_tier"] == "core") == 7
    assert sum(1 for c in batch if c["market_tier"] == "world") == 3
    # n<=0 → everything
    assert len(weekly_review_batch(companies, n=0)) == len(companies)


def test_weekly_review_batch_no_score_floor():
    """No minimum score (decision Betty, 2026-09-02): a score-0 company in
    scope still appears in the batch."""
    companies = [{"name": "Zero Co", "market_tier": "core", "assessed_score": 0.0}]
    batch = weekly_review_batch(companies, n=10)
    assert batch == companies
