"""Compact A4 delivery note (ReportLab platypus): usually one page."""
from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from bejitech.pdf.layout import MARGIN, LogoBadge, header_band, info_cards, p, page_decor, styles
from bejitech.pdf.styles import INK, LINE, MUTED, accent_from_logo, initials, tint

INSTRUCTION_LINES_SHORT = 4


def _logo(path, name, accent, size=15 * mm):
    if path and Path(path).exists():
        img = Image(str(path))
        ratio = img.imageWidth / float(img.imageHeight)
        w = min(size * ratio, 32 * mm)
        img.drawWidth, img.drawHeight = w, w / ratio
        return img
    return LogoBadge(initials(name), accent, size)


def _steps(text: str, limit: int | None) -> str:
    lines = [x.strip() for x in (text or "").splitlines() if x.strip()]
    if limit and len(lines) > limit:
        lines = lines[:limit]
    return "<br/>".join(p(x) for x in lines)


def build_delivery_note(path: Path, data: dict) -> Path:
    """Render a delivery note.

    data keys: note_number, delivery_date (display string), sales_ref, status, seller{}, customer{},
    items[ {product_name, publisher, edition, version, platform, license_type, quantity,
            keys[(key, qty)], download_url, download_label, installation, activation, logo} ],
    include_signature, footer, show_account, instructions ("short" | "full" | "none")
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    first = data["items"][0]
    accent = accent_from_logo(first.get("logo"), first.get("publisher") or first["product_name"])
    st = styles(accent)
    seller, customer = data["seller"], data["customer"]
    mode = data.get("instructions", "short")

    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN,
                            topMargin=MARGIN, bottomMargin=18 * mm,
                            title=f"Delivery note {data['note_number']}",
                            author=seller.get("name") or "", subject=first["product_name"])
    story = [
        header_band(st, accent, seller, "DELIVERY NOTE",
                    [f"No. <b>{escape(data['note_number'])}</b>", f"Date {escape(data['delivery_date'])}",
                     f"Sale ref {escape(data.get('sales_ref') or '')}"]),
        Spacer(1, 5 * mm),
        info_cards(st, [
            ("DELIVERED TO", [customer.get("name"), customer.get("organization"), customer.get("phone"),
                              customer.get("email"), customer.get("address")]),
            ("FROM", [seller.get("name"), seller.get("business_name"), seller.get("phone"), seller.get("email")]),
        ]),
        Spacer(1, 6 * mm),
    ]

    for item in data["items"]:
        meta = " · ".join(x for x in [item.get("publisher"), item.get("edition"), item.get("platform"),
                                       item.get("license_type")] if x)
        head = Table([[
            _logo(item.get("logo"), item["product_name"], accent),
            [Paragraph(p(item["product_name"]), st["product"]), Paragraph(p(meta), st["small"])],
            [Paragraph("ACTIVATIONS", st["label"]),
             Paragraph(f"Activations purchased: <b>{item['quantity']}</b>", st["body"])],
        ]], colWidths=[22 * mm, None, 48 * mm])
        head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                  ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
        key_rows = [[[Paragraph("LICENCE KEY", st["label"]), Paragraph(p(key), st["key"])],
                     Paragraph(f"{qty} activation{'s' if qty != 1 else ''}", st["small"])]
                    for key, qty in item["keys"]]
        keys = Table(key_rows, colWidths=[None, 30 * mm])
        keys.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), tint(accent, 0.93)), ("LINEBEFORE", (0, 0), (0, -1), 2.2, accent),
            ("LINEBELOW", (0, 0), (-1, -2), 0.4, tint(accent, 0.7)), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4.5 * mm), ("TOPPADDING", (0, 0), (-1, -1), 2.5 * mm),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5 * mm),
        ]))
        block = [head, Spacer(1, 3 * mm), keys, Spacer(1, 3 * mm)]
        if item.get("download_url"):
            label = item.get("download_label") or f"Download {item['product_name']}"
            href = escape(item["download_url"], {'"': "&quot;"})
            block.append(Paragraph(
                f'<font color="#{accent.hexval()[2:]}"><b>DOWNLOAD</b></font>&nbsp;&nbsp;'
                f'<link href="{href}" color="#{accent.hexval()[2:]}"><u>» {escape(label)}</u></link>', st["link"]))
            block.append(Spacer(1, 3 * mm))
        story.append(KeepTogether(block))

        if mode != "none" and (item.get("installation") or item.get("activation")):
            limit = None if mode == "full" else INSTRUCTION_LINES_SHORT
            cols = []
            for title, text in (("Installation instructions", item.get("installation")),
                                ("Activation instructions", item.get("activation"))):
                if text:
                    cols.append([Paragraph(title, st["h"]), Paragraph(_steps(text, limit), st["tiny"])])
            t = Table([cols], colWidths=[f"{100 / len(cols):.4f}%"] * len(cols))
            t.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                ("LINEAFTER", (0, 0), (-2, -1), 0.5, LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm), ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 2.5 * mm), ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
            ]))
            story += [t, Spacer(1, 5 * mm)]

    # Payment summary and signature side by side
    left, right = [], []
    account = customer.get("account")
    if account and data.get("show_account", True):
        right = _account_box(account, st, accent)
    if data.get("include_signature"):
        sig = Table([["Received by", ""], ["Signature", ""], ["Date", ""]],
                    colWidths=[22 * mm, 52 * mm], rowHeights=[9 * mm, 9 * mm, 9 * mm], hAlign="LEFT")
        sig.setStyle(TableStyle([
            ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 7.5), ("TEXTCOLOR", (0, 0), (0, -1), MUTED),
            ("VALIGN", (0, 0), (-1, -1), "BOTTOM"), ("LINEBELOW", (1, 0), (1, -1), 0.6, INK),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ]))
        left = [Paragraph("CUSTOMER CONFIRMATION", st["label"]), sig]
    if left or right:
        row = Table([[left or "", right or ""]], colWidths=["50%", "50%"])
        row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (0, -1), 0),
                                 ("RIGHTPADDING", (-1, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (0, -1), 8 * mm)]))
        story += [Spacer(1, 2 * mm), KeepTogether([row])]
    if data.get("footer"):
        story += [Spacer(1, 6 * mm), Paragraph(p(data["footer"]), st["small"])]

    left_footer = " · ".join(x for x in [seller.get("business_name") or seller.get("name"), seller.get("phone")] if x)
    on_page = page_decor(accent, left_footer, data["note_number"],
                         "VOID" if data.get("status") == "VOID" else None)
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
    t = Table(rows, colWidths=[None, 38 * mm])
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 8.5), ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("TEXTCOLOR", (0, 0), (-1, -2), INK),
        ("FONT", (0, -1), (-1, -1), "Helvetica-Bold", 10), ("TEXTCOLOR", (0, -1), (-1, -1), accent),
        ("LINEABOVE", (0, -1), (-1, -1), 0.8, accent), ("BACKGROUND", (0, -1), (-1, -1), tint(accent, 0.92)),
        ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm), ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 1.6 * mm), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6 * mm),
    ]))
    return [Paragraph("PAYMENT", st["label"]), t]
