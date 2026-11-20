"""Shared look for customer documents (delivery note, invoice): colours, text styles, header and footer."""
from __future__ import annotations

from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Flowable, Paragraph, Table, TableStyle

from bejitech.pdf.styles import INK, LINE, MUTED, SOFT, tint

PAGE_W, PAGE_H = A4
MARGIN = 16 * mm


def p(text: str | None) -> str:
    return escape(text or "").replace("\n", "<br/>")


def styles(accent) -> dict:
    base = dict(fontName="Helvetica", fontSize=9, leading=12.5, textColor=INK)
    return {
        "body": ParagraphStyle("body", **base),
        "small": ParagraphStyle("small", **{**base, "fontSize": 8, "leading": 10.5, "textColor": MUTED}),
        "tiny": ParagraphStyle("tiny", **{**base, "fontSize": 7.5, "leading": 9.8, "textColor": INK}),
        "label": ParagraphStyle("label", **{**base, "fontName": "Helvetica-Bold", "fontSize": 7,
                                            "leading": 9, "textColor": accent}),
        "brand": ParagraphStyle("brand", **{**base, "fontName": "Helvetica-Bold", "fontSize": 15, "leading": 18,
                                            "textColor": colors.white}),
        "brand_sub": ParagraphStyle("brand_sub", **{**base, "fontSize": 8, "leading": 10.5,
                                                    "textColor": tint(accent, 0.75)}),
        "title": ParagraphStyle("title", **{**base, "fontName": "Helvetica-Bold", "fontSize": 18, "leading": 21,
                                            "alignment": TA_RIGHT, "textColor": colors.white}),
        "title_meta": ParagraphStyle("title_meta", **{**base, "fontSize": 8.5, "leading": 11.5,
                                                      "alignment": TA_RIGHT, "textColor": tint(accent, 0.8)}),
        "right": ParagraphStyle("right", **{**base, "alignment": TA_RIGHT}),
        "product": ParagraphStyle("product", **{**base, "fontName": "Helvetica-Bold", "fontSize": 12.5,
                                                "leading": 15.5}),
        "key": ParagraphStyle("key", **{**base, "fontName": "Courier-Bold", "fontSize": 12.5, "leading": 16}),
        "h": ParagraphStyle("h", **{**base, "fontName": "Helvetica-Bold", "fontSize": 8.5, "leading": 11,
                                    "spaceAfter": 2, "textColor": accent}),
        "link": ParagraphStyle("link", **{**base, "fontName": "Helvetica-Bold", "fontSize": 10, "leading": 13}),
        "big": ParagraphStyle("big", **{**base, "fontName": "Helvetica-Bold", "fontSize": 17, "leading": 21,
                                        "alignment": TA_RIGHT}),
    }


class LogoBadge(Flowable):
    """Coloured square with initials, used when no logo was uploaded."""

    def __init__(self, text: str, color, size=16 * mm, fg=colors.white):
        super().__init__()
        self.text, self.color, self.size, self.fg = text, color, size, fg
        self.width = self.height = size

    def draw(self):
        c = self.canv
        c.setFillColor(self.color)
        c.roundRect(0, 0, self.size, self.size, 3 * mm, stroke=0, fill=1)
        c.setFillColor(self.fg)
        c.setFont("Helvetica-Bold", self.size * 0.36)
        c.drawCentredString(self.size / 2, self.size * 0.33, self.text)


def header_band(st, accent, seller: dict, title: str, meta_lines: list[str]) -> Table:
    """Full-width coloured band: business name and contacts on the left, document title on the right."""
    business = seller.get("business_name") or seller.get("name") or ""
    contact = " · ".join(x for x in [seller.get("phone"), seller.get("email")] if x)
    left = [Paragraph(p(business), st["brand"])]
    if seller.get("business_name") and seller.get("name"):
        left.append(Paragraph(p(seller["name"]), st["brand_sub"]))
    if contact:
        left.append(Paragraph(p(contact), st["brand_sub"]))
    if seller.get("address"):
        left.append(Paragraph(p(seller["address"]), st["brand_sub"]))
    right = [Paragraph(p(title), st["title"])] + [Paragraph(m, st["title_meta"]) for m in meta_lines]
    t = Table([[left, right]], colWidths=["58%", "42%"])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), accent), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7 * mm), ("RIGHTPADDING", (0, 0), (-1, -1), 7 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 6 * mm), ("BOTTOMPADDING", (0, 0), (-1, -1), 6 * mm),
        ("ROUNDEDCORNERS", [3 * mm, 3 * mm, 3 * mm, 3 * mm]),
    ]))
    return t


def info_cards(st, cells: list[tuple[str, list[str]]]) -> Table:
    """A row of soft cards, each with a small coloured label and some lines (first line bold)."""
    row = []
    for label, lines in cells:
        lines = [x for x in lines if x]
        body = "<br/>".join([f"<b>{p(lines[0])}</b>"] + [p(x) for x in lines[1:]]) if lines else ""
        row.append([Paragraph(label, st["label"]), Paragraph(body, st["body"])])
    t = Table([row], colWidths=[f"{100 / len(cells):.4f}%"] * len(cells))
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("BACKGROUND", (0, 0), (-1, -1), SOFT),
        ("LEFTPADDING", (0, 0), (-1, -1), 5 * mm), ("RIGHTPADDING", (0, 0), (-1, -1), 5 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5 * mm), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5 * mm),
        ("LINEAFTER", (0, 0), (-2, -1), 0.5, LINE), ("ROUNDEDCORNERS", [2 * mm, 2 * mm, 2 * mm, 2 * mm]),
    ]))
    return t


def page_decor(accent, footer_left: str, footer_right: str, watermark: str | None = None):
    def on_page(c, doc):
        c.saveState()
        c.setStrokeColor(LINE)
        c.line(MARGIN, 12 * mm, PAGE_W - MARGIN, 12 * mm)
        c.setFont("Helvetica", 7)
        c.setFillColor(MUTED)
        c.drawString(MARGIN, 8 * mm, footer_left)
        c.drawRightString(PAGE_W - MARGIN, 8 * mm, f"{footer_right} · Page {doc.page}")
        c.setFillColor(accent)
        c.rect(0, 0, PAGE_W, 2.2 * mm, stroke=0, fill=1)
        if watermark:
            c.setFillColor(colors.Color(0.85, 0.1, 0.1, alpha=0.16))
            c.setFont("Helvetica-Bold", 110)
            c.translate(PAGE_W / 2, PAGE_H / 2)
            c.rotate(35)
            c.drawCentredString(0, 0, watermark)
        c.restoreState()
    return on_page
