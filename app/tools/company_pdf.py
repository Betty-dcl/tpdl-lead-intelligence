"""Per-company PDF brief — a one-pager that mirrors the platform's company
detail page (score + formula, evolution curve, signal cards with sources,
tech stack, flags). Built on the branded TPDLPDF base from pdf_export.

A CSV can't carry the curve, the colours or clickable source links; this is the
"send it to someone" export Betty asked for. Data in → PDF bytes out; the router
assembles the company dict + trajectory points and calls generate_company_brief_pdf.
"""
from __future__ import annotations

import re
from typing import Optional

from fpdf.enums import XPos, YPos

from app.tools.pdf_export import (
    ACCENT,
    DARK_INK,
    LIGHT_BG,
    TEXT,
    TEXT_MUTED,
    WHITE,
    TPDLPDF,
    _latin1_safe,
)

# Score-band colours, matching the platform's scoreClass() buckets.
_BAND_ACT   = ((220, 247, 231), (10, 58, 38))    # >=8  green
_BAND_MON   = ((224, 231, 255), (55, 48, 163))   # 5-7  indigo
_BAND_WEAK  = ((238, 238, 238), (90, 90, 90))    # <5   grey


def _band(score: float) -> tuple[tuple, tuple]:
    if (score or 0) >= 8:
        return _BAND_ACT
    if (score or 0) >= 5:
        return _BAND_MON
    return _BAND_WEAK


_SIGNAL_LABELS = {
    "leadership_change": "Leadership change",
    "hiring": "Hiring",
    "ma_expansion": "M&A / Expansion",
    "pe_event": "PE event",
    "digital_initiative": "Digital initiative",
    "org_restructuring": "Org restructuring",
    "earnings_call_digital": "Earnings-call digital priority",
}


class CompanyPDF(TPDLPDF):
    """A company brief. Reuses TPDLPDF's branded header/footer + latin-1 safety."""

    def h1(self, text: str) -> None:
        self.set_font("Helvetica", "B", 20)
        self.set_text_color(*TEXT)
        self.set_x(self.l_margin)
        self.multi_cell(0, 9, _latin1_safe(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(1)

    def muted(self, text: str, size: int = 9) -> None:
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "", size)
        self.set_text_color(*TEXT_MUTED)
        self.multi_cell(0, 5, _latin1_safe(text), wrapmode="CHAR",
                        new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def section_label(self, text: str) -> None:
        self.ln(3)
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(*TEXT_MUTED)
        self.cell(0, 5, _latin1_safe(text.upper()), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        y = self.get_y()
        self.set_draw_color(225, 228, 227)
        self.line(self.l_margin, y, 210 - self.r_margin, y)
        self.ln(2)

    def body(self, text: str, size: int = 10) -> None:
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "", size)
        self.set_text_color(*TEXT)
        # wrapmode CHAR so an occasional long token (a URL in the summary) can't
        # raise "not enough horizontal space" — it wraps by character instead.
        self.multi_cell(0, 5.2, _latin1_safe(text or "—"), wrapmode="CHAR",
                        new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def kv(self, key: str, value: str) -> None:
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*TEXT_MUTED)
        self.cell(38, 5.2, _latin1_safe(key), new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*TEXT)
        self.multi_cell(0, 5.2, _latin1_safe(value or "—"),
                        new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # ── score hero ────────────────────────────────────────────────────────────
    def score_hero(self, score: float, coverage: str, eligible: bool,
                   icp: bool, review: bool, neotek: Optional[float],
                   delta: Optional[float]) -> None:
        bg, fg = _band(score or 0)
        x, y = self.l_margin, self.get_y()
        # big score chip
        self.set_fill_color(*bg)
        self.rect(x, y, 34, 20, "F")
        self.set_xy(x, y + 3)
        self.set_font("Helvetica", "B", 26)
        self.set_text_color(*fg)
        self.cell(34, 14, f"{(score or 0):.1f}", align="C")
        # right column: formula + status
        self.set_xy(x + 40, y)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*TEXT_MUTED)
        self.multi_cell(0, 4.4, _latin1_safe(
            "score = signal strength (0-6) + recency (0-2) + corroboration (0-2)"))
        self.set_x(x + 40)
        badges = []
        badges.append("OUTREACH-ELIGIBLE (>=8)" if eligible else "not outreach-eligible")
        if icp:
            badges.append("out of ICP")
        if review:
            badges.append("review-flagged")
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(*(DARK_INK if eligible else TEXT_MUTED))
        self.multi_cell(0, 4.6, _latin1_safe("  ·  ".join(badges)))
        self.set_x(x + 40)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*TEXT_MUTED)
        cov = (coverage or "").strip()
        line = f"coverage: {cov}" if cov else ""
        if neotek is not None:
            arrow = "->" if delta and delta > 0 else ("<-" if delta and delta < 0 else "=")
            line += f"   ·   Neotek May {neotek:.1f} {arrow} {score:.1f} (delta {delta:+.1f})" if delta is not None \
                    else f"   ·   also in Neotek May at {neotek:.1f}"
        if line:
            self.multi_cell(0, 4.6, _latin1_safe(line))
        self.set_y(max(self.get_y(), y + 22))
        self.set_x(self.l_margin)

    # ── evolution sparkline ─────────────────────────────────────────────────────
    def sparkline(self, points: list[tuple[str, float]]) -> None:
        """points = [(label, score), …] oldest→newest, scores 0..10."""
        if not points:
            return
        w = 210 - self.l_margin - self.r_margin
        h = 26
        x0, y0 = self.l_margin, self.get_y()
        # frame baseline
        self.set_draw_color(230, 232, 231)
        self.line(x0, y0 + h, x0 + w, y0 + h)
        n = len(points)
        def px(i): return x0 + (w * (i / (n - 1))) if n > 1 else x0 + w / 2
        def py(s): return y0 + h - (h - 4) * (max(0.0, min(10.0, s)) / 10.0)
        # connecting line
        self.set_draw_color(*ACCENT)
        self.set_line_width(0.7)
        for i in range(n - 1):
            self.line(px(i), py(points[i][1]), px(i + 1), py(points[i + 1][1]))
        self.set_line_width(0.2)
        # dots + labels
        for i, (label, s) in enumerate(points):
            cx, cy = px(i), py(s)
            self.set_fill_color(*DARK_INK)
            self.ellipse(cx - 1.4, cy - 1.4, 2.8, 2.8, "F")
            self.set_font("Helvetica", "B", 8)
            self.set_text_color(*TEXT)
            self.set_xy(cx - 12, cy - 6)
            self.cell(24, 4, f"{s:.1f}", align="C")
            self.set_font("Helvetica", "", 7)
            self.set_text_color(*TEXT_MUTED)
            self.set_xy(cx - 14, y0 + h + 1.5)
            self.cell(28, 4, _latin1_safe(label), align="C")
        self.set_y(y0 + h + 7)
        self.set_x(self.l_margin)

    # ── signal card ─────────────────────────────────────────────────────────────
    def signal_card(self, idx: int, sig: dict) -> None:
        cat = _SIGNAL_LABELS.get(sig.get("category", ""), sig.get("category", ""))
        conf = (sig.get("confidence") or "").strip()
        corr = sig.get("corroboration")
        # corroboration is a dict {points, max, note, url_count} in the serializer.
        if isinstance(corr, dict):
            corr_txt = f"{corr.get('points')}/{corr.get('max', 2)}"
        elif corr is not None:
            corr_txt = f"{corr}/2"
        else:
            corr_txt = None
        head = f"#{idx}  {cat}"
        if conf:
            head += f"   ·   confidence: {conf}"
        if corr_txt:
            head += f"   ·   corroboration {corr_txt}"
        self.ln(2)
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*DARK_INK)
        self.multi_cell(0, 5.4, _latin1_safe(head), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        for label, key in (("What happened", "what_happened"),
                           ("Why it matters", "why_it_matters"),
                           ("TPDL relevance", "tpdl_relevance")):
            val = (sig.get(key) or "").strip()
            if not val:
                continue
            self.set_x(self.l_margin)
            self.set_font("Helvetica", "B", 8)
            self.set_text_color(*TEXT_MUTED)
            self.cell(0, 4.6, _latin1_safe(label.upper()), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.set_font("Helvetica", "", 9)
            self.set_text_color(*TEXT)
            self.multi_cell(0, 4.8, _latin1_safe(val), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        urls = sig.get("urls") or []
        if urls:
            self.set_x(self.l_margin)
            self.set_font("Helvetica", "B", 8)
            self.set_text_color(*TEXT_MUTED)
            self.cell(0, 4.6, "SOURCES", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            for u in urls:
                # Clickable domain on one line (a full-URL multi_cell with a link
                # hangs fpdf's CHAR wrapper), then the full URL in small grey below.
                dom = re.sub(r"^https?://(www\.)?", "", u).split("/")[0][:60]
                self.set_x(self.l_margin)
                self.set_font("Helvetica", "B", 8)
                self.set_text_color(9, 71, 130)
                self.cell(0, 4.4, _latin1_safe(dom), link=u,
                          new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                self.set_font("Helvetica", "", 6.5)
                self.set_text_color(*TEXT_MUTED)
                self.multi_cell(0, 3.4, _latin1_safe(u), wrapmode="CHAR",
                                new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _render_brief(pdf: CompanyPDF, company: dict, points: list[tuple[str, float]]) -> None:
    """Render ONE company's brief onto the current page of `pdf` (caller adds the
    page). Shared by the single-company export and the multi-company view export."""
    name = company.get("name") or "Company"
    pdf.h1(name)
    rev = (company.get("revenue") or "").strip()
    rev_ok = rev and rev.lower() not in ("na", "n/a", "unknown", "-", "—", "none")
    ident = "  ·  ".join(x for x in [
        company.get("sector_bucket") or company.get("sector"),
        company.get("location"),
        company.get("website"),
        (f"Revenue: {rev}" if rev_ok else None),
        (f"Scanned: {company['run_label']}" if company.get("run_label") else None),
    ] if x)
    pdf.muted(ident)
    pdf.ln(3)

    pdf.score_hero(
        company.get("assessed_score") or 0.0,
        company.get("coverage") or "",
        bool(company.get("outreach_eligible")),
        bool(company.get("icp_flag")),
        bool(company.get("review_flag")),
        company.get("neotek_score"),
        company.get("delta"),
    )
    if company.get("review_flag") and company.get("review_flag_reason"):
        pdf.muted(f"Review flag: {company['review_flag_reason']}", size=8)

    if points:
        pdf.section_label("Score evolution")
        pdf.sparkline(points)

    if company.get("intelligence_summary"):
        pdf.section_label("Intelligence summary")
        pdf.body(company["intelligence_summary"])

    signals = company.get("signals") or []
    if signals:
        pdf.section_label(f"Signals found ({len(signals)})")
        for i, sig in enumerate(signals, 1):
            pdf.signal_card(i, sig)

    not_ev = company.get("signals_not_evidenced") or []
    if not_ev:
        pdf.section_label("Signal categories not evidenced")
        pdf.muted(", ".join(not_ev))

    if company.get("tech_stack_summary"):
        pdf.section_label("Tech stack (Step 1 scan)")
        pdf.body(company["tech_stack_summary"], size=9)

    if company.get("historical_context"):
        pdf.section_label("Historical context")
        pdf.body(company["historical_context"], size=9)


def generate_company_brief_pdf(company: dict, points: list[tuple[str, float]]) -> bytes:
    """company = serialized company dict; points = [(label, score), …]."""
    name = company.get("name") or "Company"
    pdf = CompanyPDF(subject=name, format_label="Company brief")
    pdf.add_page()
    _render_brief(pdf, company, points)
    return bytes(pdf.output())


def generate_multi_brief_pdf(items: list[tuple[dict, list]], subject: str) -> bytes:
    """items = [(company_dict, points), …]. One full brief per company, each on a
    fresh page — the detailed view export (curve + summary + signals + links)."""
    pdf = CompanyPDF(subject=subject, format_label="Company briefs")
    for company, points in items:
        pdf.add_page()
        _render_brief(pdf, company, points)
    if not items:                       # never emit a zero-page PDF
        pdf.add_page()
        pdf.muted("No companies in the current view.")
    return bytes(pdf.output())
