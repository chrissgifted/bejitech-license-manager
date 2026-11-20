import threading

import pytest
from sqlalchemy.exc import DBAPIError

from conftest import raw_execute

from bejitech.core.dto import SaleInput
from bejitech.core.errors import LicenseUnavailableError, OversellError, ValidationError


def sale(ctx, helpers, cust, qty=1, plan=None, price=85000, discount=0, product=None):
    return ctx.sales.create_sale(SaleInput(cust, product or helpers.product_id(ctx), qty, price, "MOBILE_MONEY",
                                           "2026-11-18", discount_minor=discount, plan=plan))


def test_sale_allocates_and_records_everything(ctx, helpers):
    lid = helpers.add_key(ctx, capacity=5, cost=50000)
    cust = helpers.add_customer(ctx)
    sid = sale(ctx, helpers, cust, qty=2, discount=10000)
    s = ctx.sales.get_sale(sid)
    assert s.sales_ref == "SAL-2026-00001" and s.total_minor == 160000 and s.subtotal_minor == 170000
    assert s.delivery_note_number == "DN-2026-00001"
    assert [(a.license_id, a.quantity, a.status, a.unit_cost_tzs) for a in s.allocations] == \
           [(lid, 2, "ALLOCATED", 10000)]
    lic = ctx.inventory.get_license(lid)
    assert (lic.allocated_qty, lic.remaining_qty, lic.stock_state) == (2, 3, "PARTIALLY_ALLOCATED")
    assert [h.event_type for h in ctx.inventory.history(lid)] == ["ALLOCATED"]


def test_recommendation_prefers_partial_then_fifo(ctx, helpers):
    cust = helpers.add_customer(ctx)
    a = helpers.add_key(ctx, key="AAAAA-11111", capacity=5, purchase_date="2026-10-01")
    b = helpers.add_key(ctx, key="BBBBB-22222", capacity=5, purchase_date="2026-09-01", allows_multiple_customers=True)
    # b is older → recommended first
    assert ctx.allocation.recommend(helpers.product_id(ctx), 1, cust).plan[0].license_id == b
    sale(ctx, helpers, cust, qty=1, plan=[(a, 1)])  # a becomes partial
    rec = ctx.allocation.recommend(helpers.product_id(ctx), 2, cust)
    assert rec.plan[0].license_id == a  # finish partially used key first
    assert [o.license_id for o in rec.alternatives] == [b]


def test_recommendation_prefers_expiring_soonest(ctx, helpers):
    cust = helpers.add_customer(ctx)
    helpers.add_key(ctx, key="NOEXP-00001", capacity=3)
    soon = helpers.add_key(ctx, key="SOONX-00002", capacity=3, expiration_date="2099-01-01")
    assert ctx.allocation.recommend(helpers.product_id(ctx), 1, cust).plan[0].license_id == soon


def test_split_when_no_single_key_is_enough(ctx, helpers):
    cust = helpers.add_customer(ctx)
    helpers.add_key(ctx, key="SPLIT-00001", capacity=3)
    helpers.add_key(ctx, key="SPLIT-00002", capacity=2)
    rec = ctx.allocation.recommend(helpers.product_id(ctx), 5, cust)
    assert rec.is_possible and sum(o.take for o in rec.plan) == 5 and len(rec.plan) == 2
    sid = sale(ctx, helpers, cust, qty=5)
    assert sum(a.quantity for a in ctx.sales.get_sale(sid).allocations) == 5


def test_oversell_prevented(ctx, helpers):
    lid = helpers.add_key(ctx, capacity=2)
    cust = helpers.add_customer(ctx)
    with pytest.raises(LicenseUnavailableError):
        sale(ctx, helpers, cust, qty=3)
    with pytest.raises(OversellError):
        sale(ctx, helpers, cust, qty=3, plan=[(lid, 3)])
    # nothing was written by the failed attempts
    assert ctx.inventory.get_license(lid).allocated_qty == 0
    assert ctx.sales.list_sales() == []


def test_database_rejects_oversell_even_if_code_is_bypassed(ctx, helpers):
    helpers.add_key(ctx, capacity=1)
    with pytest.raises(DBAPIError):
        raw_execute(ctx, "UPDATE licenses SET allocated_qty = 2")


def test_failed_sale_rolls_back_completely(ctx, helpers):
    a = helpers.add_key(ctx, key="ROLLB-00001", capacity=2)
    b = helpers.add_key(ctx, key="ROLLB-00002", capacity=1)
    cust = helpers.add_customer(ctx)
    with pytest.raises(OversellError):  # first allocation succeeds, second fails
        sale(ctx, helpers, cust, qty=4, plan=[(a, 2), (b, 2)])
    assert ctx.inventory.get_license(a).allocated_qty == 0
    assert ctx.sales.list_sales() == [] and ctx.delivery_notes.list_notes() == []
    assert ctx.inventory.history(a) == []
    # reference counter was rolled back too
    sid = sale(ctx, helpers, cust, qty=1)
    assert ctx.sales.get_sale(sid).sales_ref == "SAL-2026-00001"


def test_single_customer_key_not_shared(ctx, helpers):
    lid = helpers.add_key(ctx, capacity=5)  # Retail default: one customer only
    c1, c2 = helpers.add_customer(ctx, "One"), helpers.add_customer(ctx, "Two")
    sale(ctx, helpers, c1, qty=1)
    assert ctx.allocation.recommend(helpers.product_id(ctx), 1, c2).plan == []
    with pytest.raises(LicenseUnavailableError, match="another customer"):
        sale(ctx, helpers, c2, qty=1, plan=[(lid, 1)])
    sale(ctx, helpers, c1, qty=2)  # same customer may use remaining activations


def test_multi_customer_key_shared(ctx, helpers):
    lid = helpers.add_key(ctx, capacity=5, allows_multiple_customers=True)
    c1, c2 = helpers.add_customer(ctx, "One"), helpers.add_customer(ctx, "Two")
    sale(ctx, helpers, c1, qty=2)
    sale(ctx, helpers, c2, qty=3)
    assert ctx.inventory.get_license(lid).stock_state == "FULLY_ALLOCATED"


def test_expired_and_disabled_not_allocated(ctx, helpers):
    cust = helpers.add_customer(ctx)
    lid = helpers.add_key(ctx, capacity=5)
    ctx.inventory.set_disabled(lid, True, "revoked")
    with pytest.raises(LicenseUnavailableError):
        sale(ctx, helpers, cust)


def test_discount_and_validation(ctx, helpers):
    helpers.add_key(ctx)
    cust = helpers.add_customer(ctx)
    with pytest.raises(ValidationError):
        sale(ctx, helpers, cust, price=1000, discount=2000)


def test_confirm_then_cancel_keeps_capacity_used(ctx, helpers):
    lid = helpers.add_key(ctx, capacity=5, reassignable=True)
    cust = helpers.add_customer(ctx)
    sid = sale(ctx, helpers, cust, qty=2)
    alloc = ctx.sales.get_sale(sid).allocations[0]
    ctx.allocation.confirm(alloc.id)
    assert ctx.inventory.get_license(lid).confirmed_qty == 2
    opts = ctx.sales.cancellation_options(sid)
    assert not opts[0].can_release
    with pytest.raises(ValidationError):
        ctx.sales.cancel_sale(sid, "customer changed mind", {alloc.id})
    ctx.sales.cancel_sale(sid, "customer changed mind")
    lic = ctx.inventory.get_license(lid)
    assert lic.allocated_qty == 2  # consumed, not restored
    assert ctx.sales.get_sale(sid).allocations[0].status == "CONSUMED"
    assert ctx.inventory.verify_consistency() == []


def test_cancel_release_only_when_allowed(ctx, helpers):
    lid = helpers.add_key(ctx, capacity=5)  # not reassignable
    cust = helpers.add_customer(ctx)
    sid = sale(ctx, helpers, cust, qty=2)
    alloc = ctx.sales.get_sale(sid).allocations[0]
    assert not ctx.sales.cancellation_options(sid)[0].can_release
    assert ctx.sales.cancellation_options(sid, key_not_delivered=True)[0].can_release
    ctx.sales.cancel_sale(sid, "entered by mistake", {alloc.id}, key_not_delivered=True)
    assert ctx.inventory.get_license(lid).allocated_qty == 0
    s = ctx.sales.get_sale(sid)
    assert s.status == "CANCELLED" and s.allocations[0].status == "RELEASED"
    assert ctx.delivery_notes.list_notes()[0].status == "VOID"
    assert [h.event_type for h in ctx.inventory.history(lid)] == ["ALLOCATED", "RELEASED"]
    with pytest.raises(ValidationError):
        ctx.sales.cancel_sale(sid, "again")
    assert ctx.inventory.verify_consistency() == []


def test_concurrent_sales_cannot_oversell(ctx, helpers, paths, keystore):
    """Two app instances racing for the last activations: exactly one wins."""
    from bejitech.services.context import AppContext
    helpers.add_key(ctx, capacity=3, allows_multiple_customers=True)
    c1, c2 = helpers.add_customer(ctx, "One"), helpers.add_customer(ctx, "Two")
    other = AppContext.open(paths, keystore)
    other.auth.login("admin", "correct horse 1")
    results = []

    def run(c, cust):
        try:
            sale(c, helpers, cust, qty=2)
            results.append("ok")
        except (LicenseUnavailableError, OversellError):
            results.append("refused")

    t1 = threading.Thread(target=run, args=(ctx, c1))
    t2 = threading.Thread(target=run, args=(other, c2))
    t1.start(); t2.start(); t1.join(); t2.join()
    other.db.dispose()
    assert sorted(results) == ["ok", "refused"]
    assert ctx.inventory.list_licenses()[0].allocated_qty == 2
    assert ctx.inventory.verify_consistency() == []


def test_customer_history(ctx, helpers):
    helpers.add_key(ctx, capacity=5)
    cust = helpers.add_customer(ctx, phone="+255700000001", email="a@example.com")
    sale(ctx, helpers, cust, qty=1)
    sale(ctx, helpers, cust, qty=1)
    row = ctx.customers.list("+2557")[0]
    assert row.purchases == 2 and row.total_spent_minor == 170000
    assert len(ctx.customers.history(cust)) == 2
    assert ctx.customers.get(cust).customer_ref == "CUS-00001"
