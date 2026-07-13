"""PPTX export — branded TPDL deck via python-pptx.

Turns Oliver's slide outline into a clean 16:9 deck on TPDL branding.
Mirrors app/tools/pdf_export.py. Parses the same structure markers Oliver/Marc
emit: `TITLE:` / `SUBTITLE:` for the cover, `SLIDE n:` / `SECTION n —` / `H1:`
for slide headings, and `-`/`*`/`•`/`·` bullets for slide body lines.
"""
import io
import re

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

# ── TPDL brand (same palette as pdf_export.py) ──────────────────────────────
DARK_INK = RGBColor(0x09, 0x47, 0x52)   # #094752
ACCENT   = RGBColor(0x34, 0xD5, 0x91)   # #34D591
TEXT     = RGBColor(0x14, 0x14, 0x14)
MUTED    = RGBColor(0x64, 0x6E, 0x6C)
WHITE    = RGBColor(0xFF, 0xFF, 0xFF)

SLIDE_W = Inches(13.333)   # 16:9
SLIDE_H = Inches(7.5)
FONT = "Arial"

_HEAD_RE = re.compile(r"^(?:SLIDE|SECTION)\s*\d*\s*[—:\-]\s*(.*)$", re.I)
_H_RE = re.compile(r"^H[123]\s*[—:\-]\s*(.*)$", re.I)
_BULLET_CHARS = "•-*·–—"


def generate_pptx(subject: str, content: str, format_label: str = "TPDL Deck") -> bytes:
    """Return a .pptx as bytes for the given slide-outline content string."""
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H
    blank = prs.slide_layouts[6]  # fully blank layout

    title, subtitle, slides = _parse(content, subject, format_label)
    _title_slide(prs, blank, title, subtitle)

    if not slides:
        # No slide markers found — chunk the prose into bullets on one slide.
        body = [ln.strip() for ln in content.splitlines() if ln.strip()][:8]
        slides = [{"title": subject or "Overview", "body": body or ["(no content)"]}]

    for s in slides:
        _content_slide(prs, blank, s["title"], s["body"])

    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


def _parse(content: str, subject: str, format_label: str):
    title, subtitle = subject or "TPDL", format_label
    slides: list[dict] = []
    cur: dict | None = None

    for raw in content.splitlines():
        line = raw.strip()
        if not line:
            continue
        up = line.upper()

        if up.startswith("TITLE:"):
            title = line.split(":", 1)[1].strip() or title
            continue
        if up.startswith("SUBTITLE:"):
            subtitle = line.split(":", 1)[1].strip() or subtitle
            continue

        m = _HEAD_RE.match(line) or _H_RE.match(line)
        if m:
            head = m.group(1).strip()
            # "SLIDE 1: Title / one-line body" → title + first body line
            head_title, _, rest = head.partition("/")
            cur = {"title": head_title.strip() or "Slide", "body": []}
            slides.append(cur)
            if rest.strip():
                cur["body"].append(rest.strip())
            continue

        text = line.lstrip(_BULLET_CHARS).strip()
        if not text:
            continue
        if cur is None:
            cur = {"title": subject or "Overview", "body": []}
            slides.append(cur)
        cur["body"].append(text)

    return title, subtitle, slides


def _no_border(shape) -> None:
    shape.line.fill.background()


def _title_slide(prs, layout, title: str, subtitle: str) -> None:
    slide = prs.slides.add_slide(layout)
    # Full-bleed dark background
    bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SLIDE_W, SLIDE_H)
    bg.fill.solid(); bg.fill.fore_color.rgb = DARK_INK
    _no_border(bg)
    # Accent bar
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.9), Inches(3.5),
                                 Inches(1.4), Inches(0.12))
    bar.fill.solid(); bar.fill.fore_color.rgb = ACCENT
    _no_border(bar)
    # Wordmark
    _text(slide, "THE PHARMA DATA LAB", Inches(0.9), Inches(0.7), Inches(11), Inches(0.4),
          size=12, bold=True, color=ACCENT)
    # Title
    _text(slide, title, Inches(0.9), Inches(3.8), Inches(11.5), Inches(2.2),
          size=40, bold=True, color=WHITE)
    # Subtitle
    _text(slide, subtitle, Inches(0.9), Inches(2.9), Inches(11), Inches(0.6),
          size=16, bold=False, color=ACCENT)


def _content_slide(prs, layout, title: str, body: list[str]) -> None:
    slide = prs.slides.add_slide(layout)
    # Top dark bar + wordmark
    top = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SLIDE_W, Inches(0.55))
    top.fill.solid(); top.fill.fore_color.rgb = DARK_INK
    _no_border(top)
    _text(slide, "THE PHARMA DATA LAB", Inches(0.5), Inches(0.08), Inches(8), Inches(0.35),
          size=9, bold=True, color=ACCENT)
    # Accent underline under the title
    line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.6), Inches(1.55),
                                  Inches(1.0), Inches(0.06))
    line.fill.solid(); line.fill.fore_color.rgb = ACCENT
    _no_border(line)
    # Title
    _text(slide, title, Inches(0.6), Inches(0.85), Inches(12.1), Inches(0.7),
          size=26, bold=True, color=DARK_INK)
    # Body bullets
    box = slide.shapes.add_textbox(Inches(0.6), Inches(1.9), Inches(12.1), Inches(5.0))
    tf = box.text_frame
    tf.word_wrap = True
    for i, item in enumerate(body):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(10)
        run = p.add_run()
        run.text = f"•  {item}"
        run.font.size = Pt(16)
        run.font.name = FONT
        run.font.color.rgb = TEXT
    # Footer
    _text(slide, "thepharmadatalab.com", Inches(0.6), Inches(7.05), Inches(6), Inches(0.3),
          size=8, bold=False, color=MUTED)


def _text(slide, text, left, top, width, height, *, size, bold, color,
          align=PP_ALIGN.LEFT) -> None:
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.name = FONT
    run.font.color.rgb = color
