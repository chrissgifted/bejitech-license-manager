from PIL import Image
from pypdf import PdfReader

from bejitech.core.dto import SaleInput


def _sale(ctx, helpers, product=None):
    helpers.add_key(ctx, key="ABCDE-FGHIJ-KLMNO-PQRST-7HQ2D", capacity=3, product=product)
    cust = helpers.add_customer(ctx, organization="Kilimo Ltd", email="joseph@example.com")
    return ctx.sales.create_sale(SaleInput(cust, product or helpers.product_id(ctx), 2, 85000, "CASH", "2026-11-18"))


def _text(path):
    return "\n".join(p.extract_text() for p in PdfReader(str(path)).pages)


def _links(path):
    out = []
    for page in PdfReader(str(path)).pages:
        for a in page.get("/Annots") or []:
            a = a.get_object()
            if a.get("/A") and "/URI" in a["/A"]:
                out.append(a["/A"]["/URI"])
    return out


def test_pdf_contains_required_content(ctx, helpers):
    ctx.settings.update({"seller.phone": "+255 700 111 222", "seller.email": "sales@bejitech.example"})
    pid = helpers.product_id(ctx, "Windows 11 Pro")
    sid = _sale(ctx, helpers, product=pid)
    path = ctx.delivery_notes.generate_for_sale(sid)
    text = _text(path)
    for expected in ["DELIVERY NOTE", "DN-2026-00001", "Christian Joel Mtei", "Bejitech", "+255 700 111 222",
                     "Kilimo Ltd", "Windows 11 Pro", "ABCDE-FGHIJ-KLMNO-PQRST-7HQ2D", "Activations purchased: 2",
                     "Download Windows 11", "Installation instructions", "Activation instructions", "Signature",
                     "18 Nov 2026", "SAL-2026-00001"]:
        assert expected in text, expected
    # friendly label is printed, raw URL is not, but the hyperlink target is the URL
    assert "https://www.microsoft.com/software-download/windows11" not in text
    assert _links(path) == ["https://www.microsoft.com/software-download/windows11"]


def test_auto_label_when_missing(ctx, helpers):
    from bejitech.core.dto import ProductInput
    p = ctx.catalogue.get_product(helpers.product_id(ctx))
    ctx.catalogue.save_product(ProductInput(
        id=p.id, publisher_name=p.publisher, category_name=p.category, product_line_name=p.product_line,
        version=p.version, edition=p.edition, license_type_id=p.license_type_id, display_name=p.display_name,
        download_url="https://example.com/office2024"))
    sid = _sale(ctx, helpers)
    path = ctx.delivery_notes.generate_for_sale(sid)
    assert "Download Microsoft Office 2024 Professional Plus" in _text(path)
    assert _links(path) == ["https://example.com/office2024"]


def test_logo_used_and_hash_stored(ctx, helpers, tmp_path):
    pid = helpers.product_id(ctx)
    logo = tmp_path / "office.png"
    Image.new("RGB", (400, 400), (216, 59, 1)).save(logo)
    ctx.catalogue.set_logo(pid, logo)
    sid = _sale(ctx, helpers)
    path = ctx.delivery_notes.generate_for_sale(sid)
    reader = PdfReader(str(path))
    assert len(list(reader.pages[0].images)) >= 1
    note = ctx.delivery_notes.list_notes()[0]
    assert ctx.delivery_notes.pdf_file(note.id) == path


def test_tampered_pdf_is_regenerated(ctx, helpers):
    sid = _sale(ctx, helpers)
    path = ctx.delivery_notes.generate_for_sale(sid)
    path.write_bytes(b"tampered")
    note = ctx.delivery_notes.list_notes()[0]
    again = ctx.delivery_notes.pdf_file(note.id)
    assert "DELIVERY NOTE" in _text(again)


def test_new_revision_voids_old(ctx, helpers):
    sid = _sale(ctx, helpers)
    ctx.delivery_notes.generate_for_sale(sid)
    old = ctx.delivery_notes.list_notes()[0]
    ctx.settings.update({"seller.phone": "+255 711 000 000"})
    new_id = ctx.delivery_notes.new_revision(old.id)
    notes = {n.id: n for n in ctx.delivery_notes.list_notes()}
    assert notes[old.id].status == "VOID" and notes[new_id].note_number == "DN-2026-00001-R2"
    assert "+255 711 000 000" in _text(ctx.delivery_notes.pdf_file(new_id))
    assert "VOID" in _text(ctx.paths.root / notes[old.id].pdf_path)


def test_email_draft_is_honest(ctx, helpers):
    sid = _sale(ctx, helpers)
    note = ctx.delivery_notes.list_notes()[0]
    d = ctx.delivery_notes.email_draft(note.id)
    assert d["to"] == "joseph@example.com" and d["url"].startswith("mailto:joseph%40example.com?subject=")
    assert "ABCDE" not in d["body"]  # key is not put in the email body
