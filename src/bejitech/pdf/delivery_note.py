"""Premium A4 delivery note (ReportLab platypus)."""
from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Flowable, Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from bejitech.pdf.styles import INK, LINE, MUTED, SOFT, accent_from_logo, initials, tint

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm


class LogoBadge(Flowable):
    """Neutral placeholder when no approved logo was uploaded."""

    def __init__(self, text: str, color, size=24 * mm):
        super().__init__()
        self.text, self.color, self.size = text, color, size
        self.width = self.height = size

    def draw(self):
        c = self.canv
        c.setFillColor(self.color)
        c.roundRect(0, 0, self.size, self.size, 4 * mm, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", self.size * 0.36)
        c.drawCentredString(self.size / 2, self.size * 0.33, self.text)


def _p(text: str | None) -> str:
    return escape(text or "").replace("\n", "<br/>")


def _styles(accent):
    base = dict(fontName="Helvetica", fontSize=9.5, leading=13.5, textColor=INK)
    return {
        "body": ParagraphStyle("body", **base),
        "small": ParagraphStyle("small", **{**base, "fontSize": 8.5, "leading": 11.5, "textColor": MUTED}),
        "label": ParagraphStyle("label", **{**base, "fontName": "Helvetica-Bold", "fontSize": 7.5,
                                            "leading": 10, "textColor": accent}),
        "title": ParagraphStyle("title", **{**base, "fontName": "Helvetica-Bold", "fontSize": 22,
                                            "leading": 26, "alignment": TA_RIGHT}),
        "meta": ParagraphStyle("meta", **{**base, "alignment": TA_RIGHT, "textColor": MUTED}),
        "product": ParagraphStyle("product", **{**base, "fontName": "Helvetica-Bold", "fontSize": 15,
                                                "leading": 19}),
        "key": ParagraphStyle("key", **{**base, "fontName": "Courier-Bold", "fontSize": 13, "leading": 17}),
        "h": ParagraphStyle("h", **{**base, "fontName": "Helvetica-Bold", "fontSize": 10.5, "leading": 14,
                                    "spaceBefore": 4, "spaceAfter": 3, "textColor": accent}),
        "link": ParagraphStyle("link", **{**base, "fontName": "Helvetica-Bold", "fontSize": 11, "leading": 15}),
    }


def build_delivery_note(path: Path, data: dict) -> Path:
    """Render a delivery note.

    data keys: note_number, delivery_date (display string), sales_ref, status, seller{}, customer{},
    items[ {product_name, publisher, edition, version, platform, license_type, quantity,
            keys[(key, qty)], download_url, download_label, installation, activation, logo} ],
    include_signature, footer
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    first = data["items"][0]
    accent = accent_from_logo(first.get("logo"), first.get("publisher") or first["product_name"])
    st = _styles(accent)
    seller = data["seller"]
    customer = data["customer"]
    void = data.get("status") == "VOID"

    def on_page(c, doc):
        c.saveState()
        c.setFillColor(accent)
        c.rect(0, PAGE_H - 9 * mm, PAGE_W, 9 * mm, stroke=0, fill=1)
        c.setFillColor(tint(accent, 0.6))
        c.rect(0, PAGE_H - 10.5 * mm, PAGE_W, 1.5 * mm, stroke=0, fill=1)
        c.setStrokeColor(LINE)
        c.line(MARGIN, 14 * mm, PAGE_W - MARGIN, 14 * mm)
        c.setFont("Helvetica", 7.5)
        c.setFillColor(MUTED)
        left = " · ".join(x for x in [seller.get("name"), seller.get("business_name")] if x)
        c.drawString(MARGIN, 9.5 * mm, left)
        c.drawRightString(PAGE_W - MARGIN, 9.5 * mm, f"{data['note_number']} · Page {doc.page}")
        if void:
            c.setFillColor(colors.Color(0.85, 0.1, 0.1, alpha=0.18))
            c.setFont("Helvetica-Bold", 110)
            c.translate(PAGE_W / 2, PAGE_H / 2)
            c.rotate(35)
            c.drawCentredString(0, 0, "VOID")
        c.restoreState()

    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN,
                            topMargin=18 * mm, bottomMargin=20 * mm,
                            title=f"Delivery note {data['note_number']}",
                            author=seller.get("name") or "", subject=first["product_name"])
    story = []

    # Header: logo + title block
    logo_path = first.get("logo")
    if logo_path and Path(logo_path).exists():
        img = Image(str(logo_path))
        ratio = img.imageWidth / float(img.imageHeight)
        h = 24 * mm
        w = min(h * ratio, 60 * mm)
        img.drawWidth, img.drawHeight = w, w / ratio
        logo = img
    else:
        logo = LogoBadge(initials(first["product_name"]), accent)
    title = [Paragraph("DELIVERY NOTE", st["title"]),
             Paragraph(f"No. <b>{escape(data['note_number'])}</b>", st["meta"]),
             Paragraph(f"Date {escape(data['delivery_date'])}", st["meta"]),
             Paragraph(f"Sale ref {escape(data.get('sales_ref') or '')}", st["meta"])]
    header = Table([[logo, title]], colWidths=[70 * mm, None])
    header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    story += [header, Spacer(1, 8 * mm)]

    def party(label, d, name_key="name"):
        lines = [f"<b>{_p(d.get(name_key))}</b>"]
        for k in ("business_name", "organization", "phone", "email", "address"):
            if d.get(k):
                lines.append(_p(d[k]))
        return [Paragraph(label, st["label"]), Paragraph("<br/>".join(lines), st["body"])]

    parties = Table([[party("FROM", seller), party("DELIVERED TO", customer)]], colWidths=["50%", "50%"])
    parties.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("BACKGROUND", (0, 0), (-1, -1), SOFT),
        ("LEFTPADDING", (0, 0), (-1, -1), 5 * mm), ("RIGHTPADDING", (0, 0), (-1, -1), 5 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 4 * mm), ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm),
        ("LINEAFTER", (0, 0), (0, 0), 0.5, LINE),
    ]))
    story += [parties, Spacer(1, 8 * mm)]

    for item in data["items"]:
        meta = " · ".join(x for x in [item.get("publisher"), item.get("edition"), item.get("platform"),
                                       item.get("license_type")] if x)
        block = [
            Paragraph("SOFTWARE", st["label"]),
            Paragraph(_p(item["product_name"]), st["product"]),
            Paragraph(_p(meta), st["small"]),
            Spacer(1, 2 * mm),
            Paragraph(f"Activations purchased: <b>{item['quantity']}</b>", st["body"]),
            Spacer(1, 4 * mm),
        ]
        key_rows = []
        for key, qty in item["keys"]:
            key_rows.append([[Paragraph("LICENCE KEY", st["label"]), Paragraph(_p(key), st["key"])],
                             Paragraph(f"{qty} activation{'s' if qty != 1 else ''}", st["small"])])
        keys = Table(key_rows, colWidths=[None, 35 * mm])
        keys.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), tint(accent, 0.92)),
            ("BOX", (0, 0), (-1, -1), 0.8, accent), ("LINEBELOW", (0, 0), (-1, -2), 0.4, tint(accent, 0.6)),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5 * mm), ("TOPPADDING", (0, 0), (-1, -1), 3 * mm),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
        ]))
        block += [keys, Spacer(1, 6 * mm)]
        story.append(KeepTogether(block))

        if item.get("download_url"):
            label = item.get("download_label") or f"Download {item['product_name']}"
            href = escape(item["download_url"], {'"': "&quot;"})
            story += [Paragraph("DOWNLOAD", st["label"]),
                      Paragraph(f'<link href="{href}" color="#{accent.hexval()[2:]}"><u>» {escape(label)}</u></link>',
                                st["link"]),
                      Spacer(1, 5 * mm)]
        if item.get("installation"):
            story += [Paragraph("Installation instructions", st["h"]), Paragraph(_p(item["installation"]), st["body"]),
                      Spacer(1, 3 * mm)]
        if item.get("activation"):
            story += [Paragraph("Activation instructions", st["h"]), Paragraph(_p(item["activation"]), st["body"]),
                      Spacer(1, 3 * mm)]

    account = customer.get("account")
    if account and data.get("show_account", True):
        story += [Spacer(1, 2 * mm), KeepTogether(_account_box(account, st, accent))]

    if data.get("include_signature"):
        sig = Table([["Received by", "Signature", "Date"], ["", "", ""]],
                    colWidths=["40%", "35%", "25%"], rowHeights=[6 * mm, 14 * mm])
        sig.setStyle(TableStyle([
            ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 7.5), ("TEXTCOLOR", (0, 0), (-1, 0), MUTED),
            ("LINEBELOW", (0, 1), (-1, 1), 0.6, INK), ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6 * mm),
        ]))
        story += [Spacer(1, 6 * mm), KeepTogether([sig])]
    if data.get("footer"):
        story += [Spacer(1, 6 * mm), Paragraph(_p(data["footer"]), st["small"])]

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return path


def _account_box(acc: dict, st, accent) -> list:
    """Payment summary: this sale, paid now, earlier balance and what the customer owes in total."""
    from bejitech.core.money import format_money

    rows = [["This sale", format_money(acc.get("sale_total", 0))],
            ["Paid now", format_money(acc.get("paid_now", 0))]]
    prev = acc.get("previous_balance", 0)
    if prev:
        rows.append(["Earlier balance owed" if prev > 0 else "Earlier credit", format_money(abs(prev))])
    bal = acc.get("balance", 0)
    rows.append(["TOTAL BALANCE OWED" if bal >= 0 else "CREDIT ON ACCOUNT", format_money(abs(bal))])
    t = Table(rows, colWidths=[70 * mm, 45 * mm], hAlign="RIGHT")
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 9), ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONT", (0, -1), (-1, -1), "Helvetica-Bold", 10.5),
        ("LINEABOVE", (0, -1), (-1, -1), 0.8, accent), ("BOX", (0, 0), (-1, -1), 0.5, LINE),
        ("BACKGROUND", (0, -1), (-1, -1), tint(accent, 0.92)),
        ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm), ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 2 * mm), ("BOTTOMPADDING", (0, 0), (-1, -1), 2 * mm),
    ]))
    return [Paragraph("PAYMENT", st["label"]), t, Spacer(1, 4 * mm)]
