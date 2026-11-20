"""Sales: atomic creation with licence allocation, and safe cancellation."""
from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from bejitech.core.dto import AllocationView, CancelOption, SaleInput, SaleRow
from bejitech.core.enums import AllocationStatus, DeliveryNoteStatus, EntryKind, PaymentMethod, SaleStatus
from bejitech.core.errors import LicenseUnavailableError, NotFoundError, ValidationError
from bejitech.core.money import per_unit_cost
from bejitech.core.timeutil import parse_date, today_iso, utcnow_iso
from bejitech.db.models import (Customer, CustomerEntry, DeliveryNote, License, LicenseAllocation, Product,
                                 Sale, SaleItem)
from bejitech.security.masking import mask_key
from bejitech.services.accounts_service import sale_account_summary
from bejitech.services.common import audit, clean, get_setting, next_reference
from bejitech.services.inventory_service import record_event


def customer_snapshot(c: Customer, account: dict | None = None) -> str:
    data = {"name": c.full_name, "organization": c.organization, "phone": c.phone,
            "email": c.email, "address": c.address, "ref": c.customer_ref}
    if account is not None:
        data["account"] = account  # sale total, paid now, earlier balance, balance owed
    return json.dumps(data)


def seller_snapshot(s: Session) -> str:
    return json.dumps({k: get_setting(s, f"seller.{k}") for k in
                       ("name", "business_name", "phone", "email", "address")})


class SalesService:
    def __init__(self, ctx):
        self.ctx = ctx

    def create_sale(self, data: SaleInput) -> int:
        """Create a sale, allocate activations and reserve a delivery note number.

        Everything happens in ONE transaction (BEGIN IMMEDIATE). If any step fails
        nothing is saved and the inventory is unchanged.
        """
        if data.quantity < 1:
            raise ValidationError("Quantity must be at least 1.")
        if data.unit_price_minor < 0 or data.discount_minor < 0:
            raise ValidationError("Price and discount cannot be negative.")
        if (data.paid_now_minor or 0) < 0:
            raise ValidationError("The amount paid cannot be negative.")
        subtotal = data.quantity * data.unit_price_minor
        if data.discount_minor > subtotal:
            raise ValidationError("The discount cannot be larger than the subtotal.")
        try:
            PaymentMethod(data.payment_method)
        except ValueError as exc:
            raise ValidationError("Choose a payment method.") from exc
        try:
            sale_day = parse_date(data.sale_date) or parse_date(today_iso())
        except ValueError as exc:
            raise ValidationError("Sale date must be YYYY-MM-DD.") from exc

        alloc_svc = self.ctx.allocation
        with self.ctx.db.session() as s:
            customer = s.get(Customer, data.customer_id)
            if not customer or customer.is_archived:
                raise ValidationError("Please choose an active customer.")
            product = s.get(Product, data.product_id)
            if not product or product.is_archived:
                raise ValidationError("Please choose an active product.")

            plan = data.plan
            if plan is None:
                rec = alloc_svc.build_recommendation(s, product.id, data.quantity, customer.id)
                if not rec.is_possible:
                    raise LicenseUnavailableError(
                        f"Not enough activations in stock for {product.display_name}: "
                        f"{rec.total_available} available, {data.quantity} requested.")
                plan = [(o.license_id, o.take) for o in rec.plan]
            if sum(q for _, q in plan) != data.quantity:
                raise ValidationError("The selected keys do not add up to the quantity sold.")
            if len({lid for lid, _ in plan}) != len(plan):
                raise ValidationError("The same key was selected twice.")

            now = utcnow_iso()
            sale = Sale(sales_ref=next_reference(s, "SAL", sale_day), customer_id=customer.id,
                        sale_date=sale_day.isoformat(), currency="TZS", subtotal_minor=subtotal,
                        discount_minor=data.discount_minor, total_minor=subtotal - data.discount_minor,
                        payment_method=data.payment_method, payment_reference=clean(data.payment_reference),
                        status=SaleStatus.COMPLETED, notes=clean(data.notes), created_by=self.ctx.user_id,
                        created_at=now, updated_at=now)
            s.add(sale)
            s.flush()
            item = SaleItem(sale_id=sale.id, product_id=product.id, quantity=data.quantity,
                            unit_price_minor=data.unit_price_minor, discount_minor=data.discount_minor,
                            line_total_minor=subtotal - data.discount_minor)
            s.add(item)
            s.flush()
            for license_id, qty in plan:
                lic = s.get(License, license_id)
                if not lic or lic.product_id != product.id:
                    raise LicenseUnavailableError("A selected key does not belong to this product.")
                alloc_svc.allocate(s, license_id=license_id, quantity=qty, customer_id=customer.id,
                                   sale_item_id=item.id,
                                   unit_cost_tzs=per_unit_cost(lic.purchase_cost_tzs, lic.permitted_capacity),
                                   sales_ref=sale.sales_ref)
            note = DeliveryNote(note_number=next_reference(s, "DN", sale_day), sale_id=sale.id, revision=1,
                                delivery_date=sale_day.isoformat(), seller_snapshot=seller_snapshot(s),
                                customer_snapshot=customer_snapshot(customer),
                                include_signature=int(get_setting(s, "delivery.include_signature", "1") == "1"),
                                status=DeliveryNoteStatus.ISSUED, created_at=now)
            s.add(note)
            s.flush()
            if data.paid_now_minor:
                s.add(CustomerEntry(customer_id=customer.id, kind=EntryKind.PAYMENT,
                                    amount_minor=data.paid_now_minor, entry_date=sale.sale_date,
                                    method=data.payment_method, reference=clean(data.payment_reference),
                                    note=f"Paid with {sale.sales_ref}", sale_id=sale.id,
                                    created_by=self.ctx.user_id, created_at=now))
                s.flush()
            note.customer_snapshot = customer_snapshot(customer, sale_account_summary(s, sale))
            audit(s, self.ctx.user_id, "SALE_CREATED", "sale", sale.uuid, ref=sale.sales_ref,
                  product=product.display_name, quantity=data.quantity, total=sale.total_minor,
                  paid_now=data.paid_now_minor or 0)
            return sale.id

    # ---------- queries ----------
    def _row(self, s: Session, sale: Sale) -> SaleRow:
        allocs, names, qty = [], [], 0
        for it in sale.items:
            names.append(it.product.display_name)
            qty += it.quantity
            for a in it.allocations:
                allocs.append(AllocationView(a.id, a.license_id, a.license.inventory_ref,
                                             mask_key(a.license.key_suffix), a.quantity, a.status,
                                             a.unit_cost_tzs, a.confirmed_at))
        note = s.scalar(select(DeliveryNote).where(DeliveryNote.sale_id == sale.id)
                        .order_by(DeliveryNote.revision.desc()).limit(1))
        return SaleRow(sale.id, sale.uuid, sale.sales_ref, sale.sale_date, sale.customer_id,
                       sale.customer.full_name, ", ".join(names), qty, sale.subtotal_minor, sale.discount_minor,
                       sale.total_minor, sale.payment_method, sale.payment_reference, sale.status,
                       sale.cancel_reason, sale.notes, note.id if note else None,
                       note.note_number if note else None, allocs)

    def list_sales(self, search: str = "", date_from: str | None = None, date_to: str | None = None,
                   status: str | None = None, customer_id: int | None = None,
                   payment_method: str | None = None) -> list[SaleRow]:
        with self.ctx.db.session() as s:
            q = select(Sale).join(Customer)
            if date_from:
                q = q.where(Sale.sale_date >= date_from)
            if date_to:
                q = q.where(Sale.sale_date <= date_to)
            if status:
                q = q.where(Sale.status == status)
            if customer_id:
                q = q.where(Sale.customer_id == customer_id)
            if payment_method:
                q = q.where(Sale.payment_method == payment_method)
            if search:
                like = f"%{search.strip()}%"
                sub = select(SaleItem.sale_id).join(Product).where(Product.display_name.ilike(like))
                q = q.where(Sale.sales_ref.ilike(like) | Customer.full_name.ilike(like)
                            | Customer.organization.ilike(like) | Sale.payment_reference.ilike(like)
                            | Sale.id.in_(sub))
            q = q.order_by(Sale.sale_date.desc(), Sale.id.desc())
            return [self._row(s, sale) for sale in s.scalars(q)]

    def get_sale(self, sale_id: int) -> SaleRow:
        with self.ctx.db.session() as s:
            sale = s.get(Sale, sale_id)
            if not sale:
                raise NotFoundError("Sale not found.")
            return self._row(s, sale)

    # ---------- cancellation ----------
    def cancellation_options(self, sale_id: int, key_not_delivered: bool = False) -> list[CancelOption]:
        with self.ctx.db.session() as s:
            sale = s.get(Sale, sale_id)
            if not sale:
                raise NotFoundError("Sale not found.")
            return [self._cancel_option(a, key_not_delivered) for it in sale.items for a in it.allocations]

    @staticmethod
    def _cancel_option(a: LicenseAllocation, key_not_delivered: bool) -> CancelOption:
        lic = a.license
        if a.status == AllocationStatus.CONFIRMED:
            ok, why = False, "Activation was confirmed, so it is consumed."
        elif a.status != AllocationStatus.ALLOCATED:
            ok, why = False, f"Already {a.status.lower()}."
        elif key_not_delivered:
            ok, why = True, "Key was never delivered, so the activations can be returned to stock."
        elif lic.reassignable:
            ok, why = True, "Licence terms allow reassignment."
        else:
            ok, why = False, "Key was delivered and its licence terms do not allow reassignment."
        return CancelOption(a.id, lic.inventory_ref, mask_key(lic.key_suffix), a.quantity, a.status, ok, why)

    def cancel_sale(self, sale_id: int, reason: str, release_allocation_ids: set[int] | None = None,
                    key_not_delivered: bool = False) -> None:
        """Cancel a sale. Only allocations explicitly chosen AND allowed are returned to stock;
        everything else is recorded as CONSUMED (capacity stays used)."""
        if not clean(reason):
            raise ValidationError("Please give a reason for cancelling.")
        release_allocation_ids = set(release_allocation_ids or ())
        with self.ctx.db.session() as s:
            sale = s.get(Sale, sale_id)
            if not sale:
                raise NotFoundError("Sale not found.")
            if sale.status == SaleStatus.CANCELLED:
                raise ValidationError("This sale is already cancelled.")
            now = utcnow_iso()
            released, consumed = 0, 0
            for it in sale.items:
                for a in it.allocations:
                    opt = self._cancel_option(a, key_not_delivered)
                    if a.id in release_allocation_ids and not opt.can_release:
                        raise ValidationError(f"{opt.inventory_ref} cannot be returned to stock: {opt.reason}")
                    if a.status not in (AllocationStatus.ALLOCATED, AllocationStatus.CONFIRMED):
                        continue
                    lic = a.license
                    before = lic.allocated_qty
                    if a.id in release_allocation_ids:
                        lic.allocated_qty -= a.quantity
                        a.status = AllocationStatus.RELEASED
                        a.close_reason = f"Sale cancelled: {reason.strip()}"
                        event, released = "RELEASED", released + a.quantity
                    else:
                        a.status = AllocationStatus.CONSUMED
                        a.close_reason = f"Sale cancelled, not returned to stock: {opt.reason}"
                        event, consumed = "CONSUMED", consumed + a.quantity
                    a.closed_at = now
                    lic.updated_at = now
                    record_event(s, lic, event, before, self.ctx.user_id, a.id, note=sale.sales_ref)
            sale.status = SaleStatus.CANCELLED
            sale.cancelled_at = now
            sale.cancel_reason = reason.strip()
            sale.updated_at = now
            for note in s.scalars(select(DeliveryNote).where(DeliveryNote.sale_id == sale.id,
                                                             DeliveryNote.status == DeliveryNoteStatus.ISSUED)):
                note.status = DeliveryNoteStatus.VOID
                note.void_reason = f"Sale cancelled: {reason.strip()}"
            audit(s, self.ctx.user_id, "SALE_CANCELLED", "sale", sale.uuid, ref=sale.sales_ref,
                  released=released, consumed=consumed, reason=reason.strip())
