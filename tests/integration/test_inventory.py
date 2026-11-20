from datetime import date, timedelta

import pytest

from conftest import raw_execute

from bejitech.core.dto import LicenseInput
from bejitech.core.errors import ValidationError


def test_key_is_encrypted_at_rest(ctx, helpers):
    lid = helpers.add_key(ctx, key="SECRT-KEYAB-CDEFG-HIJKL-7HQ2D")
    raw = raw_execute(ctx, "SELECT * FROM licenses")[0]
    assert not any(isinstance(v, (str, bytes)) and b"SECRT" in (v if isinstance(v, bytes) else v.encode())
                   for v in raw)
    row = ctx.inventory.get_license(lid)
    assert row.masked_key == "XXXXX-XXXXX-XXXXX-XXXXX-7HQ2D"
    assert ctx.inventory.reveal_key(lid) == "SECRT-KEYAB-CDEFG-HIJKL-7HQ2D"
    actions = [a["action"] for a in ctx.audit.recent()]
    assert "KEY_REVEALED" in actions


def test_duplicate_key_rejected(ctx, helpers):
    helpers.add_key(ctx, key="AAAAA-BBBBB-CCCCC-DDDDD-EEEEE")
    with pytest.raises(ValidationError, match="already in inventory"):
        helpers.add_key(ctx, key="aaaaa-bbbbb-ccccc-ddddd-eeeee")


def test_reference_numbers_sequential(ctx, helpers):
    a = ctx.inventory.get_license(helpers.add_key(ctx, key="K1111-11111"))
    b = ctx.inventory.get_license(helpers.add_key(ctx, key="K2222-22222"))
    assert a.inventory_ref == "INV-2026-00001" and b.inventory_ref == "INV-2026-00002"


def test_usd_purchase_converted(ctx, helpers):
    lid = helpers.add_key(ctx, cost=1200, purchase_currency="USD", exchange_rate_to_tzs="2650", capacity=5)
    row = ctx.inventory.get_license(lid)
    assert row.purchase_cost_tzs == 31800 and row.exchange_rate_to_tzs == "2650"


def test_states_and_remaining(ctx, helpers):
    lid = helpers.add_key(ctx, capacity=5)
    assert ctx.inventory.get_license(lid).stock_state == "AVAILABLE"
    past = (date.today() - timedelta(days=1)).isoformat()
    exp = helpers.add_key(ctx, key="EXPRD-00000", expiration_date=past, purchase_date="2020-01-01")
    assert ctx.inventory.get_license(exp).stock_state == "EXPIRED"
    ctx.inventory.set_disabled(lid, True, "Supplier revoked")
    assert ctx.inventory.get_license(lid).stock_state == "DISABLED"
    assert [h.event_type for h in ctx.inventory.history(lid)] == ["DISABLED"]


def test_expiry_before_purchase_rejected(ctx, helpers):
    with pytest.raises(ValidationError):
        helpers.add_key(ctx, expiration_date="2026-01-01")


def test_bulk_add_is_all_or_nothing(ctx, helpers):
    helpers.add_key(ctx, key="DUPLI-CATE1")
    tmpl = LicenseInput(product_id=helpers.product_id(ctx), license_key="", purchase_date="2026-11-01",
                        purchase_cost_minor=1000, permitted_capacity=1)
    with pytest.raises(ValidationError):
        ctx.inventory.add_licenses_bulk(["NEWKY-00001", "DUPLI-CATE1"], tmpl)
    assert len(ctx.inventory.list_licenses()) == 1
    ids = ctx.inventory.add_licenses_bulk(["NEWKY-00001", "NEWKY-00002"], tmpl)
    assert len(ids) == 2


def test_capacity_cannot_drop_below_allocated(ctx, helpers):
    lid = helpers.add_key(ctx, capacity=5)
    cust = helpers.add_customer(ctx)
    from bejitech.core.dto import SaleInput
    ctx.sales.create_sale(SaleInput(cust, helpers.product_id(ctx), 3, 50000, "CASH", "2026-11-18"))
    with pytest.raises(ValidationError):
        ctx.inventory.adjust_capacity(lid, 2, "typo")
    ctx.inventory.adjust_capacity(lid, 3, "supplier corrected")
    assert ctx.inventory.get_license(lid).stock_state == "FULLY_ALLOCATED"


def test_low_stock_alerts(ctx, helpers):
    helpers.add_key(ctx, capacity=2)
    alerts = {a["display_name"] for a in ctx.inventory.low_stock_alerts()}
    assert "Microsoft Office 2024 Professional Plus" in alerts  # 2 < threshold 3
    helpers.add_key(ctx, key="MORE0-STOCK", capacity=5)
    alerts = {a["display_name"] for a in ctx.inventory.low_stock_alerts()}
    assert "Microsoft Office 2024 Professional Plus" not in alerts


def test_locked_keys_cannot_be_read(ctx, helpers):
    lid = helpers.add_key(ctx)
    ctx.auth.lock()
    from bejitech.core.errors import KeyStoreError
    with pytest.raises(KeyStoreError):
        ctx.inventory.reveal_key(lid)


def test_update_license_details(ctx, helpers):
    lid = helpers.add_key(ctx, capacity=3)
    ctx.inventory.update_license(lid, supplier_name="New Supplier", restrictions="Windows only",
                                 expiration_date="2030-12-31", notes="n", allows_multiple_customers=True,
                                 reassignable=True)
    r = ctx.inventory.get_license(lid)
    assert (r.supplier, r.restrictions, r.expiration_date, r.allows_multiple_customers) == \
           ("New Supplier", "Windows only", "2030-12-31", True)
    assert "New Supplier" in ctx.inventory.list_suppliers()
    assert [x.id for x in ctx.inventory.list_licenses("new supp")] == [lid]
    assert ctx.inventory.list_licenses(state="FULLY_ALLOCATED") == []


def test_cannot_make_shared_key_single_customer(ctx, helpers):
    from bejitech.core.dto import SaleInput
    lid = helpers.add_key(ctx, capacity=3, allows_multiple_customers=True)
    for name in ("A", "B"):
        c = helpers.add_customer(ctx, name)
        ctx.sales.create_sale(SaleInput(c, helpers.product_id(ctx), 1, 1000, "CASH", "2026-11-18"))
    with pytest.raises(ValidationError, match="several customers"):
        ctx.inventory.update_license(lid, supplier_name=None, restrictions=None, expiration_date=None,
                                     notes=None, allows_multiple_customers=False, reassignable=False)


def test_customer_archive_and_validation(ctx, helpers):
    cid = helpers.add_customer(ctx)
    ctx.customers.set_archived(cid, True)
    assert ctx.customers.list() == [] and len(ctx.customers.list(include_archived=True)) == 1
    with pytest.raises(ValidationError):
        helpers.add_customer(ctx, "X", email="not-an-email")
    with pytest.raises(ValidationError):
        helpers.add_customer(ctx, "  ")


def _edit(ctx, lid, **kw):
    r = ctx.inventory.get_license(lid)
    args = dict(supplier_name=r.supplier, restrictions=r.restrictions, expiration_date=r.expiration_date,
                notes=r.notes, allows_multiple_customers=r.allows_multiple_customers, reassignable=r.reassignable)
    args.update(kw)
    ctx.inventory.update_license(lid, **args)


def test_change_product_and_licence_type_of_unsold_key(ctx, helpers):
    from bejitech.core.dto import ProductInput
    office = helpers.product_id(ctx)
    mak = next(t["id"] for t in ctx.catalogue.list_license_types() if t["code"] == "MAK")
    p = ctx.catalogue.get_product(office)
    office_mak = ctx.catalogue.save_product(ProductInput(
        publisher_name=p.publisher, category_name=p.category, product_line_name=p.product_line,
        version=p.version, edition=p.edition, license_type_id=mak))
    lid = helpers.add_key(ctx, key="WRONG-TYPEK-00001", capacity=5)
    assert ctx.inventory.can_change_product(lid)
    _edit(ctx, lid, product_id=office_mak)
    r = ctx.inventory.get_license(lid)
    assert r.product_id == office_mak
    assert ctx.catalogue.get_product(r.product_id).license_type.startswith("MAK")
    assert ctx.inventory.reveal_key(lid) == "WRONG-TYPEK-00001"  # still decrypts after the change
    assert "PRODUCT_CHANGED" in [a["action"] for a in ctx.audit.recent()]
    # stock moved to the new product
    stock = {x["product_id"]: x["available_activations"] for x in ctx.inventory.product_stock()}
    assert stock[office_mak] == 5 and stock[office] == 0


def test_product_locked_once_sold(ctx, helpers):
    from bejitech.core.dto import SaleInput
    lid = helpers.add_key(ctx, capacity=3)
    cust = helpers.add_customer(ctx)
    sid = ctx.sales.create_sale(SaleInput(cust, helpers.product_id(ctx), 1, 1000, "CASH", "2026-11-18"))
    assert not ctx.inventory.can_change_product(lid)
    with pytest.raises(ValidationError, match="already been sold"):
        _edit(ctx, lid, product_id=helpers.product_id(ctx, "Windows 11 Pro"))
    assert ctx.inventory.get_license(lid).product_id == helpers.product_id(ctx)
    # other details can still be edited
    _edit(ctx, lid, notes="still editable", product_id=helpers.product_id(ctx))
    assert ctx.inventory.get_license(lid).notes == "still editable"
    # after a cancellation that returns the activations, the product can be corrected again
    alloc = ctx.sales.get_sale(sid).allocations[0]
    ctx.sales.cancel_sale(sid, "wrong product", {alloc.id}, key_not_delivered=True)
    assert ctx.inventory.can_change_product(lid)
    _edit(ctx, lid, product_id=helpers.product_id(ctx, "Windows 11 Pro"))
    assert ctx.inventory.get_license(lid).product_name == "Windows 11 Pro"


def test_change_licence_type_directly(ctx, helpers):
    mak = next(t["id"] for t in ctx.catalogue.list_license_types() if t["code"] == "MAK")
    lid = helpers.add_key(ctx, key="TYPEF-IELD0-00001", capacity=5)
    _edit(ctx, lid, product_id=helpers.product_id(ctx), license_type_id=mak)
    r = ctx.inventory.get_license(lid)
    p = ctx.catalogue.get_product(r.product_id)
    assert p.license_type_id == mak and p.version == "2024" and p.edition == "Professional Plus"
    assert p.display_name == "Microsoft Office 2024 Professional Plus (MAK (Multiple Activation Key))"
    assert p.installation_instructions  # copied from the original product
    # a second key with the same correction reuses that product instead of creating another
    lid2 = helpers.add_key(ctx, key="TYPEF-IELD0-00002", capacity=5)
    _edit(ctx, lid2, license_type_id=mak)
    assert ctx.inventory.get_license(lid2).product_id == r.product_id
    assert len(ctx.catalogue.list_products()) == 5


def test_licence_type_locked_once_sold(ctx, helpers):
    from bejitech.core.dto import SaleInput
    mak = next(t["id"] for t in ctx.catalogue.list_license_types() if t["code"] == "MAK")
    lid = helpers.add_key(ctx, capacity=3)
    ctx.sales.create_sale(SaleInput(helpers.add_customer(ctx), helpers.product_id(ctx), 1, 1000, "CASH", "2026-11-18"))
    with pytest.raises(ValidationError, match="already been sold"):
        _edit(ctx, lid, license_type_id=mak)
    assert len(ctx.catalogue.list_products()) == 4  # no variant created
