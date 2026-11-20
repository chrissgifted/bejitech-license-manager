from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, TableStyle

from bejitech.core.dto import Report
from bejitech.core.timeutil import display_datetime, utcnow_iso
from bejitech.pdf.styles import BRAND, INK, LINE, MUTED, SOFT


def write_report_pdf(path: Path, report: Report, seller_name: str = "") -> Path:
    path = Path(path)
    page = landscape(A4) if len(report.headers) > 6 else A4
    doc = SimpleDocTemplate(str(path), pagesize=page, leftMargin=14 * mm, rightMargin=14 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm, title=report.title)
    cell = ParagraphStyle("cell", fontName="Helvetica", fontSize=8, leading=10, textColor=INK)
    head = ParagraphStyle("head", parent=cell, fontName="Helvetica-Bold", textColor="white")
    story = [
        Paragraph(escape(report.title), ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=16, leading=20,
                                                       textColor=BRAND)),
        Paragraph(escape(f"{report.subtitle} · Generated {display_datetime(utcnow_iso())}"
                         + (f" · {seller_name}" if seller_name else "")),
                  ParagraphStyle("s", fontName="Helvetica", fontSize=9, leading=12, textColor=MUTED)),
        Spacer(1, 5 * mm),
    ]
    data = [[Paragraph(escape(str(h)), head) for h in report.headers]]
    data += [[Paragraph(escape(str(v)), cell) for v in row] for row in report.rows]
    if report.totals:
        data.append([Paragraph(f"<b>{escape(str(v))}</b>", cell) for v in report.totals])
    if len(data) == 1:
        data.append([Paragraph("No data for this period.", cell)] + [""] * (len(report.headers) - 1))
    t = LongTable(data, repeatRows=1)
    style = [("BACKGROUND", (0, 0), (-1, 0), BRAND), ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("LINEBELOW", (0, 1), (-1, -1), 0.3, LINE)]
    for i in range(2, len(data), 2):
        style.append(("BACKGROUND", (0, i), (-1, i), SOFT))
    t.setStyle(TableStyle(style))
    story.append(t)
    doc.build(story)
    return path
