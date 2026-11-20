"""Customer accounts: earlier debts, pay-later sales, payments and the balance on delivery notes."""
import json

import pytest

from conftest import raw_execute

from bejitech.core.dto import SaleInput
from bejitech.core.enums import PaymentState
from bejitech.core.errors import ValidationError


def sell(ctx, helpers, cid, key, price=100_000, paid=0, day="2026-11-10", discount=0):
    helpers.add_key(ctx, key=key)
    return ctx.sales.create_sale(SaleInput(customer_id=cid, product_id=helpers.product_id(ctx), quantity=1,
                                           unit_price_minor=price, discount_minor=discount,
                                           payment_method="MOBILE_MONEY", sale_date=day, paid_now_minor=paid))


def test_pay_later_sale_is_owed_and_part_payment(ctx, helpers):
    cid = helpers.add_customer(ctx)
    s1 = sell(ctx, helpers, cid, "AAAAA-11111", paid=0, day="2026-11-01")
    s2 = sell(ctx, helpers, cid, "BBBBB-22222", paid=40_000, day="2026-11-05")
    acc = ctx.accounts.account(cid)
    assert acc.balance_minor == 160_000 == ctx.accounts.balance(cid) == ctx.accounts.balances()[cid]
    # Money paid with a sale pays that sale
    assert acc.sales[s1].state == PaymentState.UNPAID
    assert acc.sales[s2].state == PaymentState.PARTLY_PAID and acc.sales[s2].due_minor == 60_000
    # A general payment pays the oldest debt first
    ctx.accounts.record_payment(cid, 30_000, "2026-11-06")
    assert ctx.accounts.account(cid).sales[s1].paid_minor == 30_000
    ctx.accounts.record_payment(cid, 130_000, "2026-11-20", "CASH", "R-77")
    acc = ctx.accounts.account(cid)
    assert acc.balance_minor == 0 and all(p.state == PaymentState.PAID for p in acc.sales.values())
    assert [line.balance_minor for line in acc.lines] == [100_000, 200_000, 160_000, 130_000, 0]


def test_opening_debt_is_added_and_paid_first(ctx, helpers):
    cid = helpers.add_customer(ctx)
    ctx.accounts.add_opening_debt(cid, 250_000, "2026-01-15", "Old balance from the notebook")
    sid = sell(ctx, helpers, cid, "CCCCC-33333", paid=100_000)
    acc = ctx.accounts.account(cid)
    assert acc.opening_minor == 250_000 and acc.balance_minor == 250_000
    assert acc.sales[sid].state == PaymentState.PAID  # paid with the sale: goes to this sale
    assert ctx.accounts.total_owed() == 250_000
    ctx.accounts.record_payment(cid, 100_000, "2026-11-15")  # a general payment reduces the old debt
    assert ctx.accounts.balance(cid) == 150_000


def test_delivery_note_shows_earlier_balance_and_total_owed(ctx, helpers):
    cid = helpers.add_customer(ctx)
    ctx.accounts.add_opening_debt(cid, 50_000, "2026-10-01")
    sid = sell(ctx, helpers, cid, "DDDDD-44444", price=120_000, paid=20_000)
    snap = json.loads(raw_execute(ctx, f"SELECT customer_snapshot FROM delivery_notes WHERE sale_id = {sid}")[0][0])
    assert snap["account"] == {"sale_total": 120_000, "paid_now": 20_000, "previous_balance": 50_000,
                               "balance": 150_000}
    assert ctx.delivery_notes.generate_for_sale(sid).read_bytes().startswith(b"%PDF")


def test_pay_sale_in_full_void_and_cancel(ctx, helpers):
    cid = helpers.add_customer(ctx)
    sid = sell(ctx, helpers, cid, "EEEEE-55555", price=80_000)
    eid = ctx.accounts.pay_sale_in_full(sid, "2026-11-12")
    assert ctx.accounts.balance(cid) == 0
    assert ctx.accounts.pay_sale_in_full(sid) is None  # nothing left to pay
    ctx.accounts.void_entry(eid, "Entered twice")
    assert ctx.accounts.balance(cid) == 80_000
    with pytest.raises(ValidationError):
        ctx.accounts.void_entry(eid, "again")
    # Paid, then cancelled: the money stays as credit for the next sale
    ctx.accounts.record_payment(cid, 80_000, "2026-11-13")
    ctx.sales.cancel_sale(sid, "Customer returned it")
    assert ctx.accounts.balance(cid) == -80_000
    assert ctx.accounts.total_owed() == 0


def test_invalid_amounts_are_refused(ctx, helpers):
    cid = helpers.add_customer(ctx)
    for bad in (0, -5):
        with pytest.raises(ValidationError):
            ctx.accounts.record_payment(cid, bad)
    with pytest.raises(ValidationError):
        ctx.accounts.add_opening_debt(cid, 1000, "20-11-2026")
    with pytest.raises(ValidationError):
        sell(ctx, helpers, cid, "FFFFF-66666", paid=-1)


def test_invoice_lists_what_is_owed_and_reminder_links(ctx, helpers):
    from pypdf import PdfReader
    ctx.settings.update({"invoice.payment_details": "M-Pesa Lipa: 123456 (Bejitech)"})
    cid = helpers.add_customer(ctx, phone="0712 345 678", email="amina@example.com")
    ctx.accounts.add_opening_debt(cid, 70_000, "2026-09-01", "Old balance")
    sid = sell(ctx, helpers, cid, "GGGGG-77777", price=90_000, paid=30_000)
    pdf = ctx.accounts.invoice_pdf(cid)
    text = "\n".join(pg.extract_text() for pg in PdfReader(str(pdf)).pages)
    for expected in ("INVOICE", "Old balance", "TZS 130,000", "TZS 60,000", "M-Pesa Lipa: 123456", "Amina Hassan"):
        assert expected in text, expected
    r = ctx.accounts.reminder(cid)
    assert r["whatsapp"].startswith("https://wa.me/255712345678?text=")
    assert "TZS%20130%2C000" in r["whatsapp"] and r["mailto"].startswith("mailto:amina%40example.com")
    assert ctx.accounts.account(cid).sales[sid].due_minor == 60_000
