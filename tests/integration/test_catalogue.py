import pytest
from PIL import Image

from bejitech.core.dto import ProductInput
from bejitech.core.errors import ValidationError


def _input(ctx, **kw):
    lt = ctx.catalogue.list_license_types()[0]["id"]
    base = dict(publisher_name="Microsoft", category_name="Design & Graphics", product_line_name="Visio",
                version="2021", edition="Professional", license_type_id=lt, selling_price_minor=90000)
    base.update(kw)
    return ProductInput(**base)


def test_add_search_edit_archive(ctx):
    pid = ctx.catalogue.save_product(_input(ctx))
    p = ctx.catalogue.get_product(pid)
    assert p.display_name == "Visio 2021 Professional"
    assert p.effective_download_label == "Download Visio 2021 Professional"
    assert [x.id for x in ctx.catalogue.list_products("visio")] == [pid]
    ctx.catalogue.save_product(_input(ctx, id=pid, display_name="Microsoft Visio 2021 Professional",
                                      download_url="https://example.com/visio", download_label="Get Visio"))
    p = ctx.catalogue.get_product(pid)
    assert p.display_name == "Microsoft Visio 2021 Professional" and p.effective_download_label == "Get Visio"
    ctx.catalogue.set_archived(pid, True)
    assert pid not in [x.id for x in ctx.catalogue.list_products()]
    assert pid in [x.id for x in ctx.catalogue.list_products(include_archived=True)]


def test_new_publisher_created(ctx):
    ctx.catalogue.save_product(_input(ctx, publisher_name="Corel", product_line_name="CorelDRAW",
                                      version="2024", edition="Standard"))
    assert "Corel" in ctx.catalogue.list_publishers()


def test_duplicate_product_rejected(ctx):
    ctx.catalogue.save_product(_input(ctx))
    with pytest.raises(ValidationError):
        ctx.catalogue.save_product(_input(ctx))


def test_bad_url_rejected(ctx):
    with pytest.raises(ValidationError):
        ctx.catalogue.save_product(_input(ctx, download_url="ftp://x"))


def test_logo_upload(ctx, tmp_path):
    pid = ctx.catalogue.list_products()[0].id
    src = tmp_path / "logo.png"
    Image.new("RGB", (900, 300), (216, 59, 1)).save(src)
    rel = ctx.catalogue.set_logo(pid, src)
    f = ctx.catalogue.logo_file(rel)
    assert f and f.exists()
    with Image.open(f) as img:
        assert max(img.size) <= 600
    bad = tmp_path / "x.txt"
    bad.write_text("nope")
    with pytest.raises(ValidationError):
        ctx.catalogue.set_logo(pid, bad)
