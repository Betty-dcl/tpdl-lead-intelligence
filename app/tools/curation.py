"""70/30 Europe/world curation — Nathalie's WEEKLY REVIEW BATCH.

Chantier 3/4 of the 2026-09-01 meeting recap (.claude/state.md): "si je donne
10 boîtes... 7 EU, 3 world" — 70% of what Nathalie reviews weekly should be
Europe-focus, 30% world/exploratory, so nothing emerging elsewhere is missed.
Betty confirmed (2026-09-02) the SAME 70/30 ratio also applies to the future
executive-moves phase (chantier 4) — this module is written generically
(interleave_by_tier takes any two pre-sorted lists) so that phase can reuse it
rather than duplicating the ratio logic.

Deliberately a STANDALONE batch, not folded into `app/tools/shortlist.py`:
shortlist.py's own docstring is a hard contract ("Maya OWNS it, Inès CONSUMES
it, they can never disagree") — a curation ratio in there would silently
change what Inès hands to Marketeering.ai, which nobody asked for. This is
Nathalie's personal weekly reading list, a different thing entirely.

Deterministic weighted round-robin interleave, not a hard slice-then-
concatenate and not randomness: same input → same output, always — so
Nathalie can be told exactly why company X is in this week's batch.
"""
from __future__ import annotations

DEFAULT_RATIO = (7, 3)   # core (Europe/CH/ES/Middle East) : world


def interleave_by_tier(core: list, world: list, ratio: tuple[int, int] = DEFAULT_RATIO) -> list:
    """Deterministically interleave two PRE-SORTED (best-first) lists at a
    target ratio, preserving each list's internal order. Never drops
    anything — once one side is exhausted, drains the other (curation
    ordering, never exclusion — mirrors the 2026-07-22 "géo n'exclut rien"
    rule even at this presentation layer)."""
    core_n, world_n = ratio
    out: list = []
    ci = wi = 0
    core_debt = world_debt = 0.0
    while ci < len(core) or wi < len(world):
        if ci < len(core) and core_debt <= world_debt:
            out.append(core[ci]); ci += 1; core_debt += 1 / core_n
        elif wi < len(world):
            out.append(world[wi]); wi += 1; world_debt += 1 / world_n
        else:
            out.append(core[ci]); ci += 1; core_debt += 1 / core_n
    return out


def weekly_review_batch(companies: list[dict], n: int,
                        ratio: tuple[int, int] = DEFAULT_RATIO) -> list[dict]:
    """`companies` = already score-sorted-desc serialized company dicts, each
    carrying a "market_tier" key (app.tools.icp.market_tier: "core" | "world").
    Returns the first `n` after interleaving core/world at `ratio` (n<=0 →
    everything). No score floor — the whole in-scope universe is eligible
    (decision Betty, 2026-09-02): this matches the meeting's own example
    ("here are my 10 companies, 7:3") without an extra assumption."""
    core = [c for c in companies if c.get("market_tier") == "core"]
    world = [c for c in companies if c.get("market_tier") != "core"]
    batch = interleave_by_tier(core, world, ratio)
    return batch if n <= 0 else batch[:n]
