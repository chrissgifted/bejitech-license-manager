"""Customer accounts: what each customer owes.

Balance owed = earlier debts entered by hand (OPENING_DEBT) + completed sales - payments received.
Entries are never deleted; a mistake is voided with a reason (kept in the audit log).

A payment made for a particular sale (paid at the sale, or "Mark paid") pays that sale first;
other payments pay the oldest debt first. This gives each sale a Paid / Partly paid / Not paid state. A cancelled sale no longer counts as a debt; money already paid for it stays on
the account as credit (a negative balance) and is used for the next sale.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from bejitech.core.enums import EntryKind, PaymentMethod, PaymentState, SaleStatus
from bejitech.core.errors import NotFoundError, ValidationError
from bejitech.core.timeutil import parse_date, today_iso, utcnow_iso
from bejitech.db.models import Customer, CustomerEntry, Sale
from bejitech.services.common import audit, clean


@dataclass
class SalePayment:
    sale_id: int
    total_minor: int
    paid_minor: int

    @property
    def due_minor(self) -> int:
        return self.total_minor - self.paid_minor

    @property
    def state(self) -> PaymentState:
        if self.paid_minor >= self.total_minor:
            return PaymentState.PAID
        return PaymentState.PARTLY_PAID if self.paid_minor > 0 else PaymentState.UNPAID


@dataclass
class OpenItem:
    date: str
    description: str
    amount_minor: int
    paid_minor: int
    sale_id: int | None = None

    @property
    def due_minor(self) -> int:
        return self.amount_minor - self.paid_minor


@dataclass
class StatementLine:
    date: str
    kind: str            # SALE / OPENING_DEBT / PAYMENT
    description: str
    charge_minor: int
    payment_minor: int
    balance_minor: int
    entry_id: int | None = None
    sale_id: int | None = None
    is_void: bool = False
    void_reason: str | None = None


@dataclass
class Account:
    customer_id: int
    opening_minor: int = 0
    sales_minor: int = 0
    paid_minor: int = 0
    lines: list[StatementLine] = field(default_factory=list)
    sales: dict[int, SalePayment] = field(default_factory=dict)
    open_items: list["OpenItem"] = field(default_factory=list)  # debts not yet fully paid, oldest first

    @property
    def balance_minor(self) -> int:
        return self.opening_minor + self.sales_minor - self.paid_minor


def _parse_amount(amount_minor: int) -> int:
    if not isinstance(amount_minor, int) or amount_minor <= 0:
        raise ValidationError("Enter an amount greater than zero.")
    return amount_minor


def _parse_day(text: str | None) -> str:
    try:
        d = parse_date(text) if text else None
    except ValueError as exc:
        raise ValidationError("Date must be YYYY-MM-DD.") from exc
    return (d.isoformat() if d else today_iso())


def balance_in_session(s: Session, customer_id: int, exclude_sale_id: int | None = None) -> int:
    """Balance owed, optionally leaving out one sale and the payments linked to it."""
    sales = select(func.coalesce(func.sum(Sale.total_minor), 0)).where(
        Sale.customer_id == customer_id, Sale.status == SaleStatus.COMPLETED)
    entries = select(CustomerEntry.kind, func.coalesce(func.sum(CustomerEntry.amount_minor), 0)).where(
        CustomerEntry.customer_id == customer_id, CustomerEntry.is_void == 0)
    if exclude_sale_id:
        sales = sales.where(Sale.id != exclude_sale_id)
        entries = entries.where((CustomerEntry.sale_id.is_(None)) | (CustomerEntry.sale_id != exclude_sale_id))
    total = int(s.scalar(sales) or 0)
    for kind, amount in s.execute(entries.group_by(CustomerEntry.kind)):
        total += int(amount) if kind == EntryKind.OPENING_DEBT else -int(amount)
    return total


def sale_account_summary(s: Session, sale: Sale) -> dict:
    """Figures printed on the delivery note: this sale, paid now, earlier balance, balance now."""
    paid_now = int(s.scalar(select(func.coalesce(func.sum(CustomerEntry.amount_minor), 0)).where(
        CustomerEntry.sale_id == sale.id, CustomerEntry.kind == EntryKind.PAYMENT,
        CustomerEntry.is_void == 0)) or 0)
    previous = balance_in_session(s, sale.customer_id, exclude_sale_id=sale.id)
    return {"sale_total": sale.total_minor, "paid_now": paid_now, "previous_balance": previous,
            "balance": previous + sale.total_minor - paid_now}


class AccountsService:
    def __init__(self, ctx):
        self.ctx = ctx

    # ---------- changes ----------
    def _add(self, kind: str, customer_id: int, amount_minor: int, entry_date: str | None, *, method=None,
             reference=None, note=None, sale_id=None) -> int:
        amount_minor = _parse_amount(amount_minor)
        day = _parse_day(entry_date)
        if method:
            try:
                PaymentMethod(method)
            except ValueError as exc:
                raise ValidationError("Choose a payment method.") from exc
        with self.ctx.db.session() as s:
            c = s.get(Customer, customer_id)
            if not c:
                raise NotFoundError("Customer not found.")
            if sale_id:
                sale = s.get(Sale, sale_id)
                if not sale or sale.customer_id != customer_id:
                    raise ValidationError("That sale belongs to another customer.")
            e = CustomerEntry(customer_id=customer_id, kind=kind, amount_minor=amount_minor, entry_date=day,
                              method=method if kind == EntryKind.PAYMENT else None, reference=clean(reference),
                              note=clean(note), sale_id=sale_id, created_by=self.ctx.user_id,
                              created_at=utcnow_iso())
            s.add(e)
            s.flush()
            audit(s, self.ctx.user_id, "PAYMENT_RECORDED" if kind == EntryKind.PAYMENT else "OPENING_DEBT_ADDED",
                  "customer", c.uuid, ref=c.customer_ref, amount=amount_minor, date=day)
            return e.id

    def record_payment(self, customer_id: int, amount_minor: int, entry_date: str | None = None,
                       method: str = PaymentMethod.CASH, reference: str | None = None, note: str | None = None,
                       sale_id: int | None = None) -> int:
        return self._add(EntryKind.PAYMENT, customer_id, amount_minor, entry_date, method=method,
                         reference=reference, note=note, sale_id=sale_id)

    def add_opening_debt(self, customer_id: int, amount_minor: int, entry_date: str | None = None,
                         note: str | None = None) -> int:
        return self._add(EntryKind.OPENING_DEBT, customer_id, amount_minor, entry_date,
                         note=note or "Balance brought forward")

    def pay_sale_in_full(self, sale_id: int, entry_date: str | None = None, method: str | None = None,
                         reference: str | None = None) -> int | None:
        """Record a payment for whatever is still owed on one sale. Returns None if nothing is owed."""
        with self.ctx.db.session() as s:
            sale = s.get(Sale, sale_id)
            if not sale:
                raise NotFoundError("Sale not found.")
            if sale.status != SaleStatus.COMPLETED:
                raise ValidationError("This sale is cancelled.")
            customer_id, default_method = sale.customer_id, sale.payment_method
        due = self.account(customer_id).sales.get(sale_id)
        if not due or due.due_minor <= 0:
            return None
        return self.record_payment(customer_id, due.due_minor, entry_date, method or default_method,
                                   reference, f"Payment for {self._sale_ref(sale_id)}", sale_id=sale_id)

    def void_entry(self, entry_id: int, reason: str) -> None:
        if not clean(reason):
            raise ValidationError("Please give a reason.")
        with self.ctx.db.session() as s:
            e = s.get(CustomerEntry, entry_id)
            if not e:
                raise NotFoundError("Entry not found.")
            if e.is_void:
                raise ValidationError("This entry is already void.")
            e.is_void = 1
            e.void_reason = reason.strip()
            c = s.get(Customer, e.customer_id)
            audit(s, self.ctx.user_id, "ACCOUNT_ENTRY_VOIDED", "customer", c.uuid, kind=e.kind,
                  amount=e.amount_minor, reason=reason.strip())

    def _sale_ref(self, sale_id: int) -> str:
        with self.ctx.db.session() as s:
            sale = s.get(Sale, sale_id)
            return sale.sales_ref if sale else ""

    # ---------- queries ----------
    def account(self, customer_id: int) -> Account:
        """Full statement with a running balance, and Paid / Not paid for each sale."""
        acc = Account(customer_id)
        with self.ctx.db.session() as s:
            if not s.get(Customer, customer_id):
                raise NotFoundError("Customer not found.")
            events = []  # (date, order, line)
            for sale in s.scalars(select(Sale).where(Sale.customer_id == customer_id)):
                names = ", ".join(it.product.display_name for it in sale.items)
                done = sale.status == SaleStatus.COMPLETED
                qty = sum(it.quantity for it in sale.items)
                events.append((sale.sale_date, 1, sale.id, StatementLine(
                    sale.sale_date, "SALE", f"{sale.sales_ref} · {names} × {qty}" + ("" if done else " (cancelled)"),
                    sale.total_minor if done else 0, 0, 0, sale_id=sale.id, is_void=not done,
                    void_reason=sale.cancel_reason if not done else None)))
            for e in s.scalars(select(CustomerEntry).where(CustomerEntry.customer_id == customer_id)):
                if e.kind == EntryKind.OPENING_DEBT:
                    line = StatementLine(e.entry_date, e.kind, e.note or "Balance brought forward",
                                         e.amount_minor, 0, 0, entry_id=e.id)
                    order = 0
                else:
                    how = PaymentMethod(e.method).label if e.method in PaymentMethod.__members__ else "Payment"
                    desc = "Payment received · " + how + (f" · {e.reference}" if e.reference else "") \
                        + (f" · {e.note}" if e.note else "")
                    line = StatementLine(e.entry_date, e.kind, desc, 0, e.amount_minor, 0, entry_id=e.id,
                                         sale_id=e.sale_id)
                    order = 2
                line.is_void, line.void_reason = bool(e.is_void), e.void_reason
                events.append((e.entry_date, order, e.id, line))
        events.sort(key=lambda x: (x[0], x[1], x[2]))
        running = 0
        debts = []  # [sale_id or None, amount] oldest first
        for _d, _o, _i, line in events:
            if not line.is_void:
                running += line.charge_minor - line.payment_minor
                if line.kind == "SALE":
                    acc.sales_minor += line.charge_minor
                    debts.append([line.sale_id, line.charge_minor, line])
                elif line.kind == EntryKind.OPENING_DEBT:
                    acc.opening_minor += line.charge_minor
                    debts.append([None, line.charge_minor, line])
                else:
                    acc.paid_minor += line.payment_minor
            line.balance_minor = running
            acc.lines.append(line)
        # A payment made for a particular sale pays that sale first; everything else (and any extra)
        # pays the oldest debt first.
        linked: dict[int, int] = {}
        for line in acc.lines:
            if line.kind == EntryKind.PAYMENT and not line.is_void and line.sale_id:
                linked[line.sale_id] = linked.get(line.sale_id, 0) + line.payment_minor
        paid_by_sale: dict[int, int] = {}
        pool = acc.paid_minor
        for sale_id, amount, _line in debts:
            if sale_id and sale_id in linked:
                take = min(amount, linked[sale_id])
                paid_by_sale[sale_id] = take
                pool -= take
        remaining = []  # what is still owed on each debt after its own payments
        for sale_id, amount, _line in debts:
            remaining.append([sale_id, amount - paid_by_sale.get(sale_id, 0) if sale_id else amount])
        for item in remaining:
            take = min(item[1], max(pool, 0))
            pool -= take
            item[1] -= take
        for (sale_id, amount, line), (_sid, left) in zip(debts, remaining):
            if sale_id:
                acc.sales[sale_id] = SalePayment(sale_id, amount, amount - left)
            if left > 0:
                acc.open_items.append(OpenItem(line.date, line.description, amount, amount - left, sale_id))
        return acc

    def balance(self, customer_id: int) -> int:
        with self.ctx.db.session() as s:
            return balance_in_session(s, customer_id)

    def balances(self) -> dict[int, int]:
        """Balance owed by every customer that has any account activity."""
        with self.ctx.db.session() as s:
            out: dict[int, int] = {}
            for cid, total in s.execute(select(Sale.customer_id, func.sum(Sale.total_minor))
                                        .where(Sale.status == SaleStatus.COMPLETED).group_by(Sale.customer_id)):
                out[cid] = out.get(cid, 0) + int(total or 0)
            for cid, kind, total in s.execute(
                    select(CustomerEntry.customer_id, CustomerEntry.kind, func.sum(CustomerEntry.amount_minor))
                    .where(CustomerEntry.is_void == 0).group_by(CustomerEntry.customer_id, CustomerEntry.kind)):
                out[cid] = out.get(cid, 0) + (int(total) if kind == EntryKind.OPENING_DEBT else -int(total))
            return out

    def sale_states(self, customer_ids: set[int] | None = None) -> dict[int, SalePayment]:
        """Paid / Partly paid / Not paid for each completed sale (of the given customers, or all)."""
        with self.ctx.db.session() as s:
            if customer_ids is None:
                customer_ids = set(s.scalars(select(Sale.customer_id).distinct()))
        out: dict[int, SalePayment] = {}
        for cid in customer_ids:
            out.update(self.account(cid).sales)
        return out

    def total_owed(self) -> int:
        """Money customers owe (customers in credit are not subtracted)."""
        return sum(b for b in self.balances().values() if b > 0)

    # ---------- invoice and reminder ----------
    def invoice_data(self, customer_id: int) -> dict:
        from bejitech.core.timeutil import display_date
        acc = self.account(customer_id)
        c = self.ctx.customers.get(customer_id)
        st = self.ctx.settings.all()
        today = today_iso()
        payments = [ln for ln in acc.lines if ln.kind == EntryKind.PAYMENT and not ln.is_void][-5:]
        return {
            "number": f"{c.customer_ref}-{today.replace('-', '')}",
            "date": display_date(today),
            "seller": self.ctx.settings.seller(),
            "customer": {"name": c.full_name, "organization": c.organization, "phone": c.phone, "email": c.email,
                         "address": c.address, "ref": c.customer_ref},
            "items": [{"date": display_date(i.date), "description": i.description, "amount": i.amount_minor,
                       "paid": i.paid_minor, "due": i.due_minor} for i in acc.open_items],
            "total_due": max(acc.balance_minor, 0),
            "payments": [{"date": display_date(ln.date), "description": ln.description.replace(
                "Payment received · ", ""), "amount": ln.payment_minor} for ln in reversed(payments)],
            "payment_details": st.get("invoice.payment_details", ""),
            "note": st.get("invoice.note", "") or "Kindly settle the balance at your earliest convenience. "
                                                   "Thank you for your business.",
        }

    def invoice_pdf(self, customer_id: int):
        from bejitech.pdf.invoice import build_invoice
        data = self.invoice_data(customer_id)
        out = self.ctx.paths.root / "invoices" / f"Invoice {data['number']}.pdf"
        build_invoice(out, data)
        with self.ctx.db.session() as s:
            c = s.get(Customer, customer_id)
            audit(s, self.ctx.user_id, "INVOICE_GENERATED", "customer", c.uuid, number=data["number"],
                  total_due=data["total_due"])
        return out

    def reminder(self, customer_id: int) -> dict:
        """Ready-to-send reminder text, with WhatsApp and email links (the PDF is attached by hand)."""
        from urllib.parse import quote

        from bejitech.core.money import format_money
        data = self.invoice_data(customer_id)
        seller = data["seller"]
        lines = [f"Dear {data['customer']['name']},", "",
                 f"This is a friendly reminder that your balance with {seller.get('business_name') or seller.get('name')}"
                 f" is {format_money(data['total_due'])}.", ""]
        for it in data["items"][:10]:
            lines.append(f"• {it['date']}: {it['description']} – {format_money(it['due'])}")
        if len(data["items"]) > 10:
            lines.append(f"• …and {len(data['items']) - 10} more")
        if data["payment_details"]:
            lines += ["", "How to pay:", data["payment_details"]]
        lines += ["", "Thank you.", seller.get("name") or "", seller.get("phone") or ""]
        text = "\n".join(lines).strip()
        phone = "".join(ch for ch in (data["customer"].get("phone") or "") if ch.isdigit())
        if phone.startswith("0") and len(phone) == 10:
            phone = "255" + phone[1:]  # Tanzanian local number
        subject = f"Payment reminder – invoice {data['number']}"
        email = data["customer"].get("email") or ""
        return {"text": text, "total_due": data["total_due"], "number": data["number"],
                "whatsapp": f"https://wa.me/{phone}?text={quote(text)}" if phone else
                f"https://wa.me/?text={quote(text)}",
                "has_phone": bool(phone), "email": email,
                "mailto": f"mailto:{quote(email)}?subject={quote(subject)}&body={quote(text)}"}
