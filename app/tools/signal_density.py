"""Signal density — shared by Hugo's per-company brief and Maya's portfolio
`/summary` so both read the same model the exact same way. A company with 2+
corroborated signal categories is a higher-conviction bet than a single-signal
company at an equal or even slightly higher score (external GTM benchmarks
show reply rates roughly double at that density) — see maya.md §4b.
"""


def signal_categories(c) -> list[str]:
    """Non-null signal categories on a company, in slot order (max 3)."""
    return [cat for cat in (c.s1_category, c.s2_category, c.s3_category) if cat]
