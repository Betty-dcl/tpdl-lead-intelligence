"""Generate the TPDL pixel-art avatar set (consulting edition).

Hand-crafted 20x20 pixel portraits rendered as crisp SVGs — professional
consulting wardrobe (blazers, collars, ties, turtlenecks) with TPDL brand
accents (#094752 teal / #34D591 mint). Replaces the external DiceBear
dependency: every avatar is a local static file.

Usage:  python scripts/gen_avatars.py     (writes static/img/avatars/*.svg)

Idempotent + deterministic: same code -> same SVGs. Tweak a persona here,
re-run, reload the page.
"""
from __future__ import annotations

from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "static" / "img" / "avatars"

GRID = 20  # 20x20 pixel grid

# ── palette ──────────────────────────────────────────────────────────────────
TEAL = "#094752"          # TPDL dark
MINT = "#34D591"          # TPDL accent
MINT_INK = "#0a3a26"

SKIN = {
    "light":  ("#f6d7b8", "#eec39a"),   # (base, shadow)
    "warm":   ("#eec39a", "#dda877"),
    "tan":    ("#d9a066", "#c68642"),
    "brown":  ("#a5694f", "#8d5741"),
    "deep":   ("#7a4a32", "#653b27"),
}
HAIR = {
    "black":  ("#23272b", "#3a4046"),
    "espresso": ("#33241a", "#4a3527"),
    "brown":  ("#5c4030", "#73523f"),
    "chestnut": ("#7a4a2b", "#935c38"),
    "auburn": ("#8f3f22", "#a85030"),
    "ginger": ("#b65c2e", "#cc7040"),
    "blonde": ("#cfa860", "#e0bd7d"),
    "silver": ("#9aa2a6", "#b4bcc0"),
}
CLOTH = {
    "navy":     ("#243447", "#2f4258"),
    "charcoal": ("#34393f", "#43494f"),
    "teal":     (TEAL, "#0d5b68"),
    "slate":    ("#4b5763", "#5a6875"),
    "camel":    ("#a97e50", "#b98f60"),
    "cream":    ("#efe9dd", "#e2dbcc"),
    "shirt":    ("#f7f5f0", "#e9e6de"),
}
BG = {
    "mist":  "#e9f2ee",
    "sage":  "#dfeee6",
    "sand":  "#f1ead9",
    "sky":   "#e2ecf1",
    "blush": "#f3e6de",
    "stone": "#eceae4",
    "mint":  "#e2f7ec",
}

DARK_LINE = "#1c2326"     # eyes / linework
WHITE = "#ffffff"


class Canvas:
    def __init__(self, bg: str):
        self.px: dict[tuple[int, int], str] = {}
        self.bg = bg

    def put(self, x: int, y: int, color: str) -> None:
        if 0 <= x < GRID and 0 <= y < GRID:
            self.px[(x, y)] = color

    def rect(self, x: int, y: int, w: int, h: int, color: str) -> None:
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                self.put(xx, yy, color)

    def row(self, y: int, x0: int, x1: int, color: str) -> None:
        self.rect(x0, y, x1 - x0 + 1, 1, color)

    def svg(self) -> str:
        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {GRID} {GRID}" '
            f'shape-rendering="crispEdges">',
            f'<rect width="{GRID}" height="{GRID}" fill="{self.bg}"/>',
        ]
        # merge horizontal runs of same colour into single rects (smaller files)
        for y in range(GRID):
            x = 0
            while x < GRID:
                c = self.px.get((x, y))
                if c is None:
                    x += 1
                    continue
                x2 = x
                while x2 + 1 < GRID and self.px.get((x2 + 1, y)) == c:
                    x2 += 1
                parts.append(f'<rect x="{x}" y="{y}" width="{x2 - x + 1}" height="1" fill="{c}"/>')
                x = x2 + 1
        parts.append("</svg>")
        return "".join(parts)


# ── shared anatomy ───────────────────────────────────────────────────────────

def head(c: Canvas, skin: str) -> None:
    base, shadow = SKIN[skin]
    # face block cols 6..13, rows 4..12 with soft corners
    c.rect(6, 5, 8, 7, base)
    c.row(4, 7, 12, base)
    c.row(12, 7, 12, base)
    # jaw shadow + chin
    c.row(12, 8, 11, shadow)
    c.row(11, 6, 6, shadow)
    c.row(11, 13, 13, shadow)
    # ears
    c.put(5, 8, base); c.put(5, 9, shadow)
    c.put(14, 8, base); c.put(14, 9, shadow)
    # neck
    c.rect(9, 13, 2, 1, shadow)


def eyes(c: Canvas, *, lashes: bool = False) -> None:
    c.put(8, 8, DARK_LINE)
    c.put(11, 8, DARK_LINE)
    c.put(8, 7, WHITE)      # highlight
    c.put(11, 7, WHITE)
    if lashes:
        c.put(7, 7, DARK_LINE)
        c.put(12, 7, DARK_LINE)


def brows(c: Canvas, hair: str) -> None:
    edge = HAIR[hair][0]
    c.row(6, 7, 8, edge)
    c.row(6, 11, 12, edge)


def mouth(c: Canvas, *, smile: bool = True) -> None:
    c.row(10, 9, 10, "#b06a52")
    if smile:
        c.put(8, 10, "#c98d72")
        c.put(11, 10, "#c98d72")


def blush(c: Canvas) -> None:
    c.put(7, 9, "#eabfa0")
    c.put(12, 9, "#eabfa0")


def glasses(c: Canvas, frame: str = "#2e3a40") -> None:
    """Thin spectacles: rims hugging each pupil + a bridge — not a visor."""
    lens = "#dfe9ec"                     # pale lens tint behind the pupil
    c.put(8, 7, lens); c.put(11, 7, lens)
    for x in (7, 9, 10, 12):             # side rims + bridge (9-10 join)
        c.put(x, 8, frame)
    c.put(7, 7, frame); c.put(12, 7, frame)   # top outer corners
    # pupils stay visible inside the lenses
    c.put(8, 8, DARK_LINE)
    c.put(11, 8, DARK_LINE)


def suit(c: Canvas, cloth: str, *, shirt: str = "shirt",
         tie: str | None = None, lapel: bool = True) -> None:
    base, light = CLOTH[cloth]
    sb, _ = CLOTH[shirt]
    # shoulders rows 14..19
    c.rect(3, 15, 14, 5, base)
    c.row(14, 5, 14, base)
    # shirt V
    c.rect(9, 14, 2, 3, sb)
    c.put(8, 14, sb); c.put(11, 14, sb)
    if lapel:
        c.put(7, 15, light); c.put(8, 16, light)
        c.put(12, 15, light); c.put(11, 16, light)
    if tie:
        c.rect(9, 15, 2, 1, tie)
        c.rect(9, 16, 2, 3, tie)


def blouse(c: Canvas, cloth: str, *, necklace: str | None = None) -> None:
    base, light = CLOTH[cloth]
    c.rect(3, 15, 14, 5, base)
    c.row(14, 5, 14, base)
    # collar notch
    c.put(9, 14, light); c.put(10, 14, light)
    c.put(9, 15, light); c.put(10, 15, light)
    if necklace:
        c.put(9, 16, necklace); c.put(10, 16, necklace)


def turtleneck(c: Canvas, cloth: str) -> None:
    base, light = CLOTH[cloth]
    c.rect(3, 15, 14, 5, base)
    c.row(14, 5, 14, base)
    c.rect(8, 13, 4, 2, light)   # rolled collar over the neck


# ── hair styles (drawn AFTER face so they overlap the top of the head) ──────

def hair_short_pro(c: Canvas, col: str) -> None:
    """Neat short business cut with a hint of a side part."""
    base, hi = HAIR[col]
    c.row(3, 7, 12, base)
    c.row(4, 6, 13, base)
    c.row(5, 6, 7, base); c.row(5, 12, 13, base)
    c.put(6, 6, base); c.put(13, 6, base)
    c.put(6, 7, base); c.put(13, 7, base)
    c.row(3, 8, 9, hi)           # side-part sheen


def hair_side_part(c: Canvas, col: str) -> None:
    """Classic consultant side part with swept fringe."""
    base, hi = HAIR[col]
    c.row(3, 7, 12, base)
    c.row(4, 6, 13, base)
    c.row(5, 6, 9, base); c.row(5, 12, 13, base)
    c.put(6, 6, base); c.put(13, 6, base); c.put(6, 7, base)
    c.row(4, 10, 12, hi)         # swept highlight


def hair_bob(c: Canvas, col: str) -> None:
    """Sharp chin-length bob."""
    base, hi = HAIR[col]
    c.row(3, 7, 12, base)
    c.row(4, 6, 13, base)
    c.rect(5, 5, 2, 6, base)
    c.rect(13, 5, 2, 6, base)
    c.put(5, 11, base); c.put(14, 11, base)
    c.row(5, 7, 8, base)         # fringe left
    c.row(3, 9, 11, hi)


def hair_bun(c: Canvas, col: str, *, streak: str | None = None) -> None:
    """Pulled-back hair with a high bun — precise and composed."""
    base, hi = HAIR[col]
    c.row(3, 7, 12, base)
    c.row(4, 6, 13, base)
    c.row(5, 6, 6, base); c.row(5, 13, 13, base)
    c.rect(8, 1, 4, 2, base)     # the bun
    c.row(1, 9, 10, hi)
    if streak:
        c.put(11, 3, streak); c.put(12, 4, streak)


def hair_ponytail(c: Canvas, col: str) -> None:
    """Sleek ponytail, tail attached at the side of the head."""
    base, hi = HAIR[col]
    c.row(3, 7, 12, base)
    c.row(4, 6, 13, base)
    c.row(5, 6, 7, base); c.row(5, 12, 13, base)
    c.rect(14, 4, 1, 6, base)    # tail hugging the head
    c.put(15, 6, base); c.put(15, 7, base); c.put(15, 8, base)
    c.put(14, 10, base)          # tapered tip
    c.row(3, 8, 10, hi)
    c.put(15, 6, hi)             # sheen on the tail


def hair_curly(c: Canvas, col: str) -> None:
    """Natural curls with volume."""
    base, hi = HAIR[col]
    c.row(2, 7, 12, base)
    c.row(3, 6, 13, base)
    c.row(4, 5, 14, base)
    c.rect(5, 5, 2, 4, base)
    c.rect(13, 5, 2, 4, base)
    c.put(6, 2, base); c.put(13, 2, base)
    c.put(7, 1, base); c.put(12, 1, base)
    c.row(2, 9, 10, hi)


def hair_waves(c: Canvas, col: str) -> None:
    """Shoulder waves tucked behind the ears."""
    base, hi = HAIR[col]
    c.row(3, 7, 12, base)
    c.row(4, 6, 13, base)
    c.rect(5, 5, 2, 7, base)
    c.rect(13, 5, 2, 7, base)
    c.put(4, 8, base); c.put(15, 8, base)
    c.put(4, 11, base); c.put(15, 11, base)
    c.row(3, 8, 9, hi)


def beard(c: Canvas, col: str) -> None:
    base, _ = HAIR[col]
    c.row(11, 7, 7, base); c.row(11, 12, 12, base)
    c.row(12, 7, 12, base)
    c.put(8, 11, base); c.put(11, 11, base)
    # keep the mouth visible
    c.row(10, 9, 10, "#b06a52")


def headset(c: Canvas, color: str = "#2e3a40", mic: str = MINT) -> None:
    c.row(2, 8, 11, color)          # band
    c.put(7, 3, color)
    c.put(14, 8, color); c.put(14, 9, color)   # earcup
    c.put(14, 10, mic); c.put(13, 11, mic)     # mic boom
    c.put(12, 11, mic)


def earrings(c: Canvas, color: str = MINT) -> None:
    c.put(5, 10, color)
    c.put(14, 10, color)


def pocket_square(c: Canvas, color: str = MINT) -> None:
    c.put(6, 17, color)


def pin(c: Canvas, color: str = MINT) -> None:
    c.put(13, 16, color)


# ── the cast ────────────────────────────────────────────────────────────────

def alex() -> Canvas:
    """Team manager — navy suit, mint tie, composed short cut."""
    c = Canvas(BG["mist"])
    head(c, "warm")
    suit(c, "navy", tie=MINT)
    eyes(c); brows(c, "espresso"); mouth(c)
    hair_short_pro(c, "espresso")
    return c


def hugo() -> Canvas:
    """Deep research — glasses, chestnut side part, teal blazer."""
    c = Canvas(BG["sky"])
    head(c, "light")
    suit(c, "teal", tie=None)
    pin(c)
    eyes(c); brows(c, "chestnut"); mouth(c)
    glasses(c)
    hair_side_part(c, "chestnut")
    return c


def maya() -> Canvas:
    """Analyst — sharp black bob, charcoal blazer, mint pocket square."""
    c = Canvas(BG["sage"])
    head(c, "tan")
    suit(c, "charcoal")
    pocket_square(c)
    eyes(c, lashes=True); brows(c, "black"); mouth(c); blush(c)
    hair_bob(c, "black")
    return c


def ines() -> Canvas:
    """Contacts — curls + headset, slate blouse."""
    c = Canvas(BG["blush"])
    head(c, "brown")
    blouse(c, "slate", necklace=None)
    eyes(c, lashes=True); brows(c, "black"); mouth(c)
    hair_curly(c, "black")
    headset(c)
    return c


def julie() -> Canvas:
    """Outreach — blonde bob, camel blazer, mint earrings."""
    c = Canvas(BG["sand"])
    head(c, "light")
    suit(c, "camel")
    eyes(c, lashes=True); brows(c, "blonde"); mouth(c); blush(c)
    hair_bob(c, "blonde")
    earrings(c)
    return c


def iris() -> Canvas:
    """Marketing intel — auburn ponytail, cream turtleneck."""
    c = Canvas(BG["mint"])
    head(c, "warm")
    turtleneck(c, "cream")
    eyes(c, lashes=True); brows(c, "auburn"); mouth(c)
    hair_ponytail(c, "auburn")
    return c


def marc() -> Canvas:
    """Content architect — trimmed beard, open collar, charcoal jacket."""
    c = Canvas(BG["stone"])
    head(c, "warm")
    suit(c, "charcoal", lapel=True)
    eyes(c); brows(c, "brown"); mouth(c)
    beard(c, "brown")
    hair_side_part(c, "brown")
    return c


def oliver() -> Canvas:
    """Format producer — ginger crop, dark turtleneck (art-director energy)."""
    c = Canvas(BG["sage"])
    head(c, "light")
    turtleneck(c, "navy")
    eyes(c); brows(c, "ginger"); mouth(c)
    hair_short_pro(c, "ginger")
    return c


def vera() -> Canvas:
    """QA — silver-streaked bun, glasses, teal high collar. Nothing escapes her."""
    c = Canvas(BG["sky"])
    head(c, "tan")
    turtleneck(c, "teal")
    eyes(c, lashes=True); brows(c, "black"); mouth(c, smile=False)
    glasses(c)
    hair_bun(c, "black", streak=HAIR["silver"][0])
    return c


# humans (the team logging in) — same style, softer wardrobe
def marie() -> Canvas:
    c = Canvas(BG["sand"])
    head(c, "light")
    blouse(c, "teal", necklace=MINT)
    eyes(c, lashes=True); brows(c, "chestnut"); mouth(c); blush(c)
    hair_waves(c, "chestnut")
    return c


def pierre() -> Canvas:
    c = Canvas(BG["sky"])
    head(c, "warm")
    suit(c, "slate", tie=TEAL)
    eyes(c); brows(c, "black"); mouth(c)
    hair_short_pro(c, "black")
    return c


def sophie() -> Canvas:
    c = Canvas(BG["mint"])
    head(c, "tan")
    suit(c, "navy")
    pocket_square(c)
    eyes(c, lashes=True); brows(c, "espresso"); mouth(c)
    hair_ponytail(c, "espresso")
    return c


def lea() -> Canvas:
    c = Canvas(BG["blush"])
    head(c, "light")
    turtleneck(c, "slate")
    eyes(c, lashes=True); brows(c, "auburn"); mouth(c); blush(c)
    hair_bob(c, "auburn")
    return c


def tomas() -> Canvas:
    c = Canvas(BG["stone"])
    head(c, "brown")
    suit(c, "charcoal", tie=MINT)
    eyes(c); brows(c, "black"); mouth(c)
    beard(c, "black")
    hair_short_pro(c, "black")
    return c


def guest() -> Canvas:
    c = Canvas(BG["mist"])
    head(c, "warm")
    suit(c, "slate")
    eyes(c); brows(c, "brown"); mouth(c)
    hair_short_pro(c, "brown")
    return c


# seed -> painter. Keys are the EXACT avatar_seed values used in DB/templates.
AVATARS = {
    "manager-alex": alex,
    "hugo-tpdl-research": hugo,
    "maya-tpdl-analyst": maya,
    "ines-tpdl-contacts": ines,
    "julie-tpdl-outreach": julie,
    "iris-tpdl-marketing-intel": iris,
    "marc-tpdl-content": marc,
    "oliver-tpdl-format": oliver,
    "vera-tpdl-quality": vera,
    "marie-user": marie,
    "pierre-user": pierre,
    "sophie-user": sophie,
    "lea-user": lea,
    "tomas-user": tomas,
    "guest-tpdl": guest,
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for seed, painter in AVATARS.items():
        svg = painter().svg()
        (OUT / f"{seed}.svg").write_text(svg, encoding="utf-8")
        print(f"wrote {seed}.svg ({len(svg)} bytes)")
    print(f"\n{len(AVATARS)} avatars in {OUT}")


if __name__ == "__main__":
    main()
