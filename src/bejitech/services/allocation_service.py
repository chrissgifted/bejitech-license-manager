"""Smart licence allocation: find, rank and recommend keys for a sale."""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from bejitech.core.dto import AllocationOption, Recommendation
from bejitech.core.enums import AllocationStatus, LicenseStatus
from bejitech.core.errors import LicenseUnavailableError, NotFoundError, ValidationError
from bejitech.core.timeutil import parse_date, utcnow_iso
from bejitech.db.models import License, LicenseAllocation
from bejitech.security.masking import mask_key
from bejitech.services.common import audit
from bejitech.services.inventory_service import USED_STATUSES, record_event, remaining


def other_customer_holds(s: Session, lic: License, customer_id: int) -> bool:
    return s.scalar(select(LicenseAllocation.id).where(
        LicenseAllocation.license_id == lic.id,
        LicenseAllocation.status.in_(USED_STATUSES),
        LicenseAllocation.customer_id != customer_id).limit(1)) is not None


def ineligibility_reason(s: Session, lic: License, customer_id: int, today: date | None = None) -> str | None:
    """Return why a key cannot be allocated to this customer, or None if it can."""
    today = today or date.today()
    if lic.status != LicenseStatus.ACTIVE:
        return f"{lic.inventory_ref} is disabled."
    exp = parse_date(lic.expiration_date)
    if exp and exp < today:
        return f"{lic.inventory_ref} expired on {lic.expiration_date}."
    if remaining(lic) <= 0:
        return f"{lic.inventory_ref} has no activations left."
    if not lic.allows_multiple_customers and other_customer_holds(s, lic, customer_id):
        return (f"{lic.inventory_ref} already belongs to another customer and its licence terms "
                "do not allow several customers.")
    return None


def rank_key(lic: License):
    exp = parse_date(lic.expiration_date)
    return (
        exp or date.max,                 # expiring soonest first
        0 if lic.allocated_qty > 0 else 1,  # finish partially used keys first
        lic.purchase_date,               # oldest stock first (FIFO)
        lic.id,
    )


class AllocationService:
    def __init__(self, ctx):
        self.ctx = ctx

    def eligible_licenses(self, s: Session, product_id: int, customer_id: int) -> list[License]:
        candidates = s.scalars(select(License).where(
            License.product_id == product_id, License.status == LicenseStatus.ACTIVE,
            License.allocated_qty < License.permitted_capacity))
        ok = [l for l in candidates if ineligibility_reason(s, l, customer_id) is None]
        return sorted(ok, key=rank_key)

    def build_recommendation(self, s: Session, product_id: int, quantity: int, customer_id: int) -> Recommendation:
        if quantity < 1:
            raise ValidationError("Quantity must be at least 1.")
        eligible = self.eligible_licenses(s, product_id, customer_id)
        total = sum(remaining(l) for l in eligible)
        rec = Recommendation(product_id=product_id, quantity=quantity, total_available=total)

        def option(l: License, take: int, reason: str) -> AllocationOption:
            return AllocationOption(l.id, l.inventory_ref, mask_key(l.key_suffix), remaining(l), take,
                                    l.expiration_date, reason)

        singles = [l for l in eligible if remaining(l) >= quantity]
        if singles:
            best = singles[0]
            why = []
            if best.expiration_date:
                why.append("expires soonest")
            if best.allocated_qty > 0:
                why.append("finishes a partly used key")
            why.append("one key covers the whole quantity")
            rec.plan = [option(best, quantity, ", ".join(why).capitalize())]
            rec.alternatives = [option(l, quantity, "") for l in singles[1:]]
            return rec
        need = quantity
        for l in eligible:
            if need == 0:
                break
            take = min(remaining(l), need)
            rec.plan.append(option(l, take, "Split across keys: no single key has enough activations"))
            need -= take
        rec.shortfall = need
        return rec

    def recommend(self, product_id: int, quantity: int, customer_id: int) -> Recommendation:
        with self.ctx.db.session() as s:
            return self.build_recommendation(s, product_id, quantity, customer_id)

    def all_options(self, product_id: int, customer_id: int) -> list[AllocationOption]:
        with self.ctx.db.session() as s:
            return [AllocationOption(l.id, l.inventory_ref, mask_key(l.key_suffix), remaining(l), 0,
                                     l.expiration_date) for l in self.eligible_licenses(s, product_id, customer_id)]

    def allocate(self, s: Session, *, license_id: int, quantity: int, customer_id: int, sale_item_id: int,
                 unit_cost_tzs: int, sales_ref: str) -> LicenseAllocation:
        """Allocate inside the caller's transaction. Re-checks everything against fresh data."""
        lic = s.get(License, license_id, populate_existing=True)
        if not lic:
            raise NotFoundError("Licence not found.")
        reason = ineligibility_reason(s, lic, customer_id)
        if reason:
            raise LicenseUnavailableError(reason)
        if quantity > remaining(lic):
            from bejitech.core.errors import OversellError
            raise OversellError(
                f"{lic.inventory_ref} has only {remaining(lic)} activation(s) left; {quantity} requested.")
        before = lic.allocated_qty
        lic.allocated_qty = before + quantity
        lic.updated_at = utcnow_iso()
        alloc = LicenseAllocation(license_id=lic.id, sale_item_id=sale_item_id, customer_id=customer_id,
                                  quantity=quantity, unit_cost_tzs=unit_cost_tzs,
                                  status=AllocationStatus.ALLOCATED, allocated_at=utcnow_iso())
        s.add(alloc)
        s.flush()
        record_event(s, lic, "ALLOCATED", before, self.ctx.user_id, alloc.id, note=sales_ref)
        return alloc

    def confirm(self, allocation_id: int) -> None:
        """Mark an allocation as confirmed (customer activated successfully)."""
        with self.ctx.db.session() as s:
            a = s.get(LicenseAllocation, allocation_id)
            if not a:
                raise NotFoundError("Allocation not found.")
            if a.status != AllocationStatus.ALLOCATED:
                raise ValidationError(f"Only allocated activations can be confirmed (this one is {a.status.lower()}).")
            lic = a.license
            a.status = AllocationStatus.CONFIRMED
            a.confirmed_at = utcnow_iso()
            lic.confirmed_qty += a.quantity
            record_event(s, lic, "CONFIRMED", lic.allocated_qty, self.ctx.user_id, a.id,
                         note=f"{a.quantity} activation(s) confirmed")
            audit(s, self.ctx.user_id, "ACTIVATION_CONFIRMED", "license", lic.uuid, allocation=a.uuid)
