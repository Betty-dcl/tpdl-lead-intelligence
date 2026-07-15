"""PDF export — branded TPDL A4 document via fpdf2.

Converts Marc's text output into a clean, styled PDF.
"""
import logging
import re
from typing import Optional

from fpdf import FPDF

logger = logging.getLogger(__name__)

# ── TPDL brand colours (RGB) ──────────────────────────────────────────────────
DARK_INK   = (9,  71,  82)   # #094752
ACCENT     = (52, 213, 145)  # #34D591
LIGHT_BG   = (245, 247, 246) # near-white
TEXT       = (20,  20,  20)
TEXT_MUTED = (100, 110, 108)
WHITE      = (255, 255, 255)


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


# fpdf2's core fonts (Helvetica) only support Latin-1. Any other codepoint —
# arrows, em-dashes, curly quotes, €, ≥, … — raises and 500s the export. Map the
# common ones to ASCII, then guarantee the rest can't crash via a final encode.
_UNICODE_MAP = {
    "—": " - ", "–": "-", "‘": "'", "’": "'", "“": '"', "”": '"',
    "•": "*", "…": "...", "→": "->", "←": "<-", "↑": "^", "↓": "v",
    "≥": ">=", "≤": "<=", "≈": "~", "×": "x", "÷": "/", "™": "(TM)",
    "®": "(R)", "©": "(C)", "€": "EUR", "£": "GBP", "°": " deg",
    " ": " ", " ": " ", " ": " ", "–": "-", "—": " - ",
}


def _latin1_safe(text: str) -> str:
    """Make text safe for fpdf2's core font — never raises, worst case '?'."""
    for uni, ascii_ in _UNICODE_MAP.items():
        text = text.replace(uni, ascii_)
    # Safety net: anything still outside Latin-1 becomes '?' instead of crashing.
    return text.encode("latin-1", "replace").decode("latin-1")


def generate_pdf(
    subject: str,
    content: str,
    format_label: str = "TPDL Report",
) -> bytes:
    """Return a PDF as bytes for the given content string."""
    pdf = TPDLPDF(subject=subject, format_label=format_label)
    pdf.add_page()
    pdf.render_content(content)
    return bytes(pdf.output())


class TPDLPDF(FPDF):
    def __init__(self, subject: str, format_label: str):
        super().__init__(orientation="P", unit="mm", format="A4")
        # subject + format_label flow into header/footer cells — sanitise them too,
        # or a Unicode char in the title crashes every page render.
        self.subject = _latin1_safe(subject)
        self.format_label = _latin1_safe(format_label)
        self.set_auto_page_break(auto=True, margin=20)
        self.set_margins(20, 28, 20)

    # ── Header / Footer ───────────────────────────────────────────────────────

    def header(self):
        # Top accent bar
        self.set_fill_color(*DARK_INK)
        self.rect(0, 0, 210, 10, "F")

        # TPDL wordmark
        self.set_xy(20, 12)
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*ACCENT)
        self.cell(0, 5, "THE PHARMA DATA LAB", ln=False)

        # Format label right-aligned
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*TEXT_MUTED)
        self.set_xy(0, 12)
        self.cell(190, 5, self.format_label, align="R")

        self.ln(6)

    def footer(self):
        self.set_y(-14)
        # Bottom accent line
        self.set_fill_color(*ACCENT)
        self.rect(0, self.get_y(), 210, 1, "F")
        self.set_y(-12)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(*TEXT_MUTED)
        self.cell(0, 5, f"thepharmadatalab.com  ·  {self.subject[:60]}", align="C")
        self.set_xy(0, self.get_y())
        self.set_font("Helvetica", "", 7)
        self.cell(190, 5, f"Page {self.page_no()}", align="R")

    # ── Content renderer ──────────────────────────────────────────────────────

    def render_content(self, content: str) -> None:
        # Sanitise unicode chars unsupported by core Helvetica (never crashes).
        content = _latin1_safe(content)
        lines = content.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i].rstrip()

            # Blank line
            if not line:
                self.ln(3)
                i += 1
                continue

            # TITLE: or SUBTITLE:
            if line.startswith("TITLE:") or line.startswith("SUBTITLE:"):
                key, _, val = line.partition(":")
                val = val.strip()
                if key == "TITLE":
                    self._render_doc_title(val)
                else:
                    self._render_doc_subtitle(val)
                i += 1
                continue

            # SECTION N — Title  or  H1/H2:
            if re.match(r"^(SECTION\s+\d+|H[123]|SLIDE\s+\d+)\s*[—:\-]", line, re.I):
                self._render_section_heading(line)
                i += 1
                continue

            # META TITLE / META DESCRIPTION
            if line.startswith("META "):
                self._render_meta_line(line)
                i += 1
                continue

            # Bullet
            if line.startswith(("•", "-", "*", "·")):
                self._render_bullet(line.lstrip("•-*· ").strip())
                i += 1
                continue

            # Bold marker **text**
            if "**" in line:
                self._render_bold_inline(line)
                i += 1
                continue

            # Plain paragraph
            self._render_paragraph(line)
            i += 1

    # ── Low-level helpers ─────────────────────────────────────────────────────

    def _render_doc_title(self, text: str) -> None:
        self.ln(4)
        self.set_fill_color(*DARK_INK)
        self.rect(20, self.get_y(), 170, 0.8, "F")
        self.ln(3)
        self.set_font("Helvetica", "B", 18)
        self.set_text_color(*DARK_INK)
        self.multi_cell(0, 9, text)
        self.ln(2)

    def _render_doc_subtitle(self, text: str) -> None:
        self.set_font("Helvetica", "I", 12)
        self.set_text_color(*TEXT_MUTED)
        self.multi_cell(0, 6, text)
        self.ln(4)
        # Accent separator
        self.set_fill_color(*ACCENT)
        self.rect(20, self.get_y(), 40, 1.5, "F")
        self.ln(5)

    def _render_section_heading(self, line: str) -> None:
        self.ln(4)
        # Accent dot
        self.set_fill_color(*ACCENT)
        self.rect(20, self.get_y() + 1.5, 4, 4, "F")
        self.set_x(26)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*DARK_INK)
        self.multi_cell(0, 6, line)
        self.ln(1)

    def _render_meta_line(self, line: str) -> None:
        self.set_fill_color(*LIGHT_BG)
        self.set_x(20)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*TEXT_MUTED)
        self.multi_cell(0, 5, line, fill=True)
        self.ln(1)

    def _render_bullet(self, text: str) -> None:
        self.set_x(24)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*TEXT)
        # Bullet symbol
        self.cell(5, 5, "·")
        self.set_x(29)
        self.multi_cell(0, 5, text)

    def _render_bold_inline(self, line: str) -> None:
        """Render a line that may contain **bold** markers."""
        parts = re.split(r"\*\*(.+?)\*\*", line)
        self.set_x(20)
        for j, part in enumerate(parts):
            if not part:
                continue
            if j % 2 == 1:  # bold segment
                self.set_font("Helvetica", "B", 10)
            else:
                self.set_font("Helvetica", "", 10)
            self.set_text_color(*TEXT)
            self.write(5, part)
        self.ln(5)

    def _render_paragraph(self, text: str) -> None:
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*TEXT)
        self.set_x(20)
        self.multi_cell(0, 5.5, text)
        self.ln(1)
