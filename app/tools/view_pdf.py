"""Designed snapshot of a table view (Recurring / Sales) — a branded landscape
PDF of exactly the rows the user is looking at, in their sort order, with their
filters already applied. The client posts the visible columns + rows (WYSIWYG);
this renders them. Pairs with the client-side CSV export for the same view.
"""
from __future__ import annotations

from fpdf import FPDF
from fpdf.enums import XPos, YPos
from fpdf.fonts import FontFace

from app.tools.pdf_export import ACCENT, DARK_INK, TEXT, TEXT_MUTED, _latin1_safe


class ViewPDF(FPDF):
    """Landscape A4 with the TPDL header/footer, for wide tables."""

    def __init__(self, title: str, subtitle: str = ""):
        super().__init__(orientation="L", unit="mm", format="A4")
        self.title_txt = _latin1_safe(title)
        self.subtitle_txt = _latin1_safe(subtitle)
        self.set_auto_page_break(auto=True, margin=16)
        self.set_margins(12, 22, 12)

    def header(self):
        self.set_fill_color(*DARK_INK)
        self.rect(0, 0, 297, 9, "F")
        self.set_xy(12, 11)
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*ACCENT)
        self.cell(0, 5, "THE PHARMA DATA LAB", new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*TEXT_MUTED)
        self.set_xy(0, 11)
        self.cell(285, 5, self.subtitle_txt, align="R")
        # title line
        self.set_xy(12, 15.5)
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(*TEXT)
        self.cell(0, 6, self.title_txt, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(1)

    def footer(self):
        self.set_y(-11)
        self.set_fill_color(*ACCENT)
        self.rect(0, self.get_y(), 297, 1, "F")
        self.set_y(-9)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(*TEXT_MUTED)
        self.cell(0, 5, "thepharmadatalab.com", align="C")
        self.set_xy(0, self.get_y())
        self.cell(285, 5, f"Page {self.page_no()}", align="R")


def generate_view_pdf(title: str, subtitle: str, columns: list[str],
                      rows: list[list], widths: list[float] | None = None) -> bytes:
    """columns = header strings; rows = list of row lists (any scalar).
    widths = optional relative column weights (defaults to equal)."""
    pdf = ViewPDF(title=title, subtitle=subtitle)
    pdf.add_page()

    ncol = len(columns)
    if widths and len(widths) == ncol:
        total = sum(widths) or 1
        col_widths = tuple((w / total) for w in widths)
    else:
        col_widths = tuple(1 / ncol for _ in range(ncol)) if ncol else (1,)

    pdf.set_font("Helvetica", "", 8)
    pdf.set_draw_color(220, 223, 222)
    headings_style = FontFace(emphasis="BOLD", color=(255, 255, 255), fill_color=DARK_INK)

    # Convert relative weights to the fraction of available width fpdf expects.
    avail = pdf.epw
    abs_widths = [max(8.0, avail * f) for f in col_widths]

    with pdf.table(col_widths=tuple(abs_widths), text_align="LEFT",
                   headings_style=headings_style, line_height=5.2,
                   first_row_as_headings=True, wrapmode="CHAR") as table:
        hrow = table.row()
        for h in columns:
            hrow.cell(_latin1_safe(str(h)))
        for r in rows:
            trow = table.row()
            for cell in r:
                trow.cell(_latin1_safe("" if cell is None else str(cell)))

    return bytes(pdf.output())
