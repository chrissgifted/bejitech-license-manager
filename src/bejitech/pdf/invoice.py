"""Invoice / payment reminder: what a customer still owes, item by item, and how to pay."""
from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from bejitech.core.money import format_money
from bejitech.pdf.layout import MARGIN, header_band, info_cards, p, page_decor, styles
from bejitech.pdf.styles import BRAND, INK, LINE, MUTED, SOFT, tint


def build_invoice(path: Path, data: dict) -> Path:
    """data: number, date (display), seller{}, customer{}, items[{date, description, amount, paid, due}],
    total_due, payments[{date, description, amount}], payment_details, note"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    accent = BRAND
    st = styles(accent)
    seller, customer = data["seller"], data["customer"]
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN,
                            topMargin=MARGIN, bottomMargin=18 * mm, title=f"Invoice {data['number']}",
                            author=seller.get("name") or "", subject="Payment reminder")
    story = [
        header_band(st, accent, seller, "INVOICE",
                    [f"No. <b>{escape(data['number'])}</b>", f"Date {escape(data['date'])}",
                     "Statement of amount due"]),
        Spacer(1, 5 * mm),
        info_cards(st, [
            ("BILL TO", [customer.get("name"), customer.get("organization"), customer.get("phone"),
                         customer.get("email"), customer.get("address")]),
            ("AMOUNT DUE", [format_money(data["total_due"]), f"Customer ref {customer.get('ref') or ''}"]),
        ]),
        Spacer(1, 7 * mm),
        Paragraph("ITEMS NOT YET PAID", st["label"]),
        Spacer(1, 1.5 * mm),
    ]

    head = ["Date", "Description", "Amount", "Paid", "Balance due"]
    rows = [head] + [[it["date"], Paragraph(p(it["description"]), st["body"]), format_money(it["amount"]),
                      format_money(it["paid"]) if it["paid"] else "—", format_money(it["due"])]
                     for it in data["items"]]
    if not data["items"]:
        rows.append(["", Paragraph("Nothing is owed. Thank you!", st["body"]), "", "", ""])
    t = Table(rows, colWidths=[22 * mm, None, 28 * mm, 26 * mm, 30 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 7.5), ("TEXTCOLOR", (0, 0), (-1, 0), MUTED),
        ("BACKGROUND", (0, 0), (-1, 0), SOFT), ("LINEBELOW", (0, 0), (-1, 0), 0.6, LINE),
        ("FONT", (0, 1), (-1, -1), "Helvetica", 8.5), ("TEXTCOLOR", (0, 1), (-1, -1), INK),
        ("FONT", (4, 1), (4, -1), "Helvetica-Bold", 8.5),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 2.2 * mm), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2 * mm),
    ]))
    story.append(t)

    total = Table([["TOTAL AMOUNT DUE", format_money(data["total_due"])]], colWidths=[None, 50 * mm], hAlign="RIGHT")
    total.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica-Bold", 12), ("TEXTCOLOR", (0, 0), (-1, -1), accent),
        ("BACKGROUND", (0, 0), (-1, -1), tint(accent, 0.9)), ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5 * mm), ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5 * mm), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5 * mm),
        ("LINEABOVE", (0, 0), (-1, 0), 1.2, accent),
    ]))
    story += [Spacer(1, 3 * mm), total, Spacer(1, 7 * mm)]

    blocks = []
    if data.get("payment_details"):
        blocks.append([Paragraph("HOW TO PAY", st["label"]), Paragraph(p(data["payment_details"]), st["body"])])
    if data.get("payments"):
        lines = "<br/>".join(f"{escape(x['date'])} · {format_money(x['amount'])} · {p(x['description'])}"
                             for x in data["payments"])
        blocks.append([Paragraph("RECENT PAYMENTS RECEIVED", st["label"]), Paragraph(lines, st["small"])])
    if blocks:
        b = Table([blocks], colWidths=[f"{100 / len(blocks):.4f}%"] * len(blocks))
        b.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOX", (0, 0), (-1, -1), 0.5, LINE),
            ("LINEAFTER", (0, 0), (-2, -1), 0.5, LINE),
            ("LEFTPADDING", (0, 0), (-1, -1), 5 * mm), ("RIGHTPADDING", (0, 0), (-1, -1), 5 * mm),
            ("TOPPADDING", (0, 0), (-1, -1), 3.5 * mm), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5 * mm),
        ]))
        story += [KeepTogether([b]), Spacer(1, 6 * mm)]
    if data.get("note"):
        story.append(Paragraph(p(data["note"]), st["body"]))

    left_footer = " · ".join(x for x in [seller.get("business_name") or seller.get("name"), seller.get("phone")] if x)
    on_page = page_decor(accent, left_footer, data["number"])
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return path
