"""Licence-key inventory and activation tracking."""
from __future__ import annotations

from datetime import date

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from bejitech.core.dto import HistoryRow, LicenseInput, LicenseRow
from bejitech.core.enums import AllocationStatus, LicenseStatus, StockState
from bejitech.core.errors import NotFoundError, ValidationError
from bejitech.core.money import convert_to_tzs, parse_rate
from bejitech.core.timeutil import parse_date, utcnow_iso
from bejitech.db.models import (
    AllocationEvent, Customer, License, LicenseAllocation, LicenseType, Product, Sale, SaleItem, Supplier,
)
from bejitech.security.masking import last_chars, mask_key, normalize_key
from bejitech.services.common import audit, clean, next_reference

USED_STATUSES = (AllocationStatus.ALLOCATED, AllocationStatus.CONFIRMED, AllocationStatus.CONSUMED)


def stock_state(lic: License, today: date | None = None) -> StockState:
    today = today or date.today()
    if lic.status == LicenseStatus.DISABLED:
        return StockState.DISABLED
    exp = parse_date(lic.expiration_date)
    if exp and exp < today:
        return StockState.EXPIRED
    if lic.allocated_qty == 0:
        return StockState.AVAILABLE
    if lic.allocated_qty < lic.permitted_capacity:
        return StockState.PARTIALLY_ALLOCATED
    return StockState.FULLY_ALLOCATED


def remaining(lic: License) -> int:
    """R1: Remaining activations = permitted capacity − allocated activations."""
    return lic.permitted_capacity - lic.allocated_qty


def record_event(s: Session, lic: License, event_type: str, before: int, user_id: int | None,
                 allocation_id: int | None = None, note: str | None = None) -> None:
    s.add(AllocationEvent(
        license_id=lic.id, allocation_id=allocation_id, event_type=event_type,
        qty_delta=lic.allocated_qty - before, allocated_before=before, allocated_after=lic.allocated_qty,
        note=note, user_id=user_id, created_at=utcnow_iso(),
    ))


class InventoryService:
    def __init__(self, ctx):
        self.ctx = ctx

    # ---------- suppliers ----------
    def list_suppliers(self) -> list[str]:
        with self.ctx.db.session() as s:
            return list(s.scalars(select(Supplier.name).where(Supplier.is_archived == 0).order_by(Supplier.name)))

    @staticmethod
    def _supplier(s: Session, name: str | None) -> Supplier | None:
        name = clean(name)
        if not name:
            return None
        sup = s.scalar(select(Supplier).where(func.lower(Supplier.name) == name.lower()))
        if not sup:
            now = utcnow_iso()
            sup = Supplier(name=name, created_at=now, updated_at=now)
            s.add(sup)
            s.flush()
        return sup

    # ---------- registration ----------
    def _validate(self, data: LicenseInput) -> None:
        key = normalize_key(data.license_key or "")
        if len(key.replace("-", "")) < 5:
            raise ValidationError("The licence key looks too short.")
        if data.permitted_capacity < 1:
            raise ValidationError("Permitted activations must be at least 1.")
        if data.purchase_cost_minor < 0:
            raise ValidationError("Purchase cost cannot be negative.")
        if data.purchase_currency not in ("TZS", "USD"):
            raise ValidationError("Purchase currency must be TZS or USD.")
        if data.purchase_currency == "USD":
            parse_rate(data.exchange_rate_to_tzs)
        try:
            pd = parse_date(data.purchase_date)
            exp = parse_date(data.expiration_date)
        except ValueError as exc:
            raise ValidationError("Dates must be in YYYY-MM-DD format.") from exc
        if not pd:
            raise ValidationError("Purchase date is required.")
        if exp and exp < pd:
            raise ValidationError("Expiry date cannot be before the purchase date.")

    def _insert(self, s: Session, data: LicenseInput) -> License:
        cipher = self.ctx.require_cipher()
        self._validate(data)
        product = s.get(Product, data.product_id)
        if not product:
            raise ValidationError("Please choose a product.")
        ltype = s.get(LicenseType, product.license_type_id)
        key = data.license_key.strip()
        fp = cipher.fingerprint(key)
        existing = s.scalar(select(License.inventory_ref).where(License.key_fingerprint == fp))
        if existing:
            raise ValidationError(f"This licence key is already in inventory ({existing}).")
        rate = "1" if data.purchase_currency == "TZS" else str(parse_rate(data.exchange_rate_to_tzs))
        now = utcnow_iso()
        lic = License(
            inventory_ref=next_reference(s, "INV", parse_date(data.purchase_date)),
            product_id=product.id,
            supplier_id=(sup.id if (sup := self._supplier(s, data.supplier_name)) else None),
            key_ciphertext=b"", key_nonce=b"", key_suffix=last_chars(key), key_fingerprint=fp,
            purchase_date=data.purchase_date[:10], purchase_cost_minor=data.purchase_cost_minor,
            purchase_currency=data.purchase_currency, exchange_rate_to_tzs=rate,
            purchase_cost_tzs=convert_to_tzs(data.purchase_cost_minor, data.purchase_currency, rate),
            permitted_capacity=data.permitted_capacity, allocated_qty=0, confirmed_qty=0,
            allows_multiple_customers=int(ltype.allows_multiple_customers if data.allows_multiple_customers is None
                                          else data.allows_multiple_customers),
            reassignable=int(ltype.reassignable if data.reassignable is None else data.reassignable),
            restrictions=clean(data.restrictions), expiration_date=clean(data.expiration_date),
            status=LicenseStatus.ACTIVE, notes=clean(data.notes), created_at=now, updated_at=now,
        )
        s.add(lic)
        s.flush()  # assigns uuid default
        lic.key_ciphertext, lic.key_nonce = cipher.encrypt_license_key(key, lic.uuid)
        audit(s, self.ctx.user_id, "CREATE", "license", lic.uuid, ref=lic.inventory_ref,
              product=product.display_name, capacity=lic.permitted_capacity)
        return lic

    def add_license(self, data: LicenseInput) -> int:
        with self.ctx.db.session() as s:
            return self._insert(s, data).id

    def add_licenses_bulk(self, keys: list[str], template: LicenseInput) -> list[int]:
        """Add several keys with the same details. All-or-nothing."""
        keys = [k.strip() for k in keys if k.strip()]
        if not keys:
            raise ValidationError("Enter at least one licence key.")
        if len({normalize_key(k) for k in keys}) != len(keys):
            raise ValidationError("The list contains the same key more than once.")
        ids = []
        with self.ctx.db.session() as s:
            for k in keys:
                data = LicenseInput(**{**template.__dict__, "license_key": k})
                ids.append(self._insert(s, data).id)
        return ids

    # ---------- queries ----------
    def _row(self, lic: License) -> LicenseRow:
        return LicenseRow(
            id=lic.id, uuid=lic.uuid, inventory_ref=lic.inventory_ref, product_id=lic.product_id,
            product_name=lic.product.display_name, supplier=lic.supplier.name if lic.supplier else None,
            masked_key=mask_key(lic.key_suffix), key_suffix=lic.key_suffix,
            permitted_capacity=lic.permitted_capacity, allocated_qty=lic.allocated_qty,
            confirmed_qty=lic.confirmed_qty, remaining_qty=remaining(lic),
            stock_state=stock_state(lic).value, status=lic.status, purchase_date=lic.purchase_date,
            purchase_cost_minor=lic.purchase_cost_minor, purchase_currency=lic.purchase_currency,
            exchange_rate_to_tzs=lic.exchange_rate_to_tzs, purchase_cost_tzs=lic.purchase_cost_tzs,
            allows_multiple_customers=bool(lic.allows_multiple_customers), reassignable=bool(lic.reassignable),
            restrictions=lic.restrictions, expiration_date=lic.expiration_date, notes=lic.notes,
            disabled_reason=lic.disabled_reason,
        )

    def list_licenses(self, search: str = "", state: str | None = None,
                      product_id: int | None = None) -> list[LicenseRow]:
        with self.ctx.db.session() as s:
            q = select(License).join(Product).outerjoin(Supplier)
            if product_id:
                q = q.where(License.product_id == product_id)
            if search:
                like = f"%{search.strip()}%"
                q = q.where(License.inventory_ref.ilike(like) | Product.display_name.ilike(like)
                            | Supplier.name.ilike(like) | License.key_suffix.ilike(like)
                            | License.notes.ilike(like))
            rows = [self._row(l) for l in s.scalars(q.order_by(License.id.desc()))]
        if state:
            rows = [r for r in rows if r.stock_state == state]
        return rows

    def get_license(self, license_id: int) -> LicenseRow:
        with self.ctx.db.session() as s:
            lic = s.get(License, license_id)
            if not lic:
                raise NotFoundError("Licence not found.")
            return self._row(lic)

    def history(self, license_id: int) -> list[HistoryRow]:
        with self.ctx.db.session() as s:
            q = (select(AllocationEvent, Customer.full_name, Sale.sales_ref)
                 .outerjoin(LicenseAllocation, LicenseAllocation.id == AllocationEvent.allocation_id)
                 .outerjoin(Customer, Customer.id == LicenseAllocation.customer_id)
                 .outerjoin(SaleItem, SaleItem.id == LicenseAllocation.sale_item_id)
                 .outerjoin(Sale, Sale.id == SaleItem.sale_id)
                 .where(AllocationEvent.license_id == license_id).order_by(AllocationEvent.id))
            return [HistoryRow(e.created_at, e.event_type, e.qty_delta, e.allocated_before, e.allocated_after,
                               cust, ref, e.note) for e, cust, ref in s.execute(q)]

    # ---------- changes ----------
    @staticmethod
    def _has_used_allocations(s: Session, lic: License) -> bool:
        return s.scalar(select(LicenseAllocation.id).where(
            LicenseAllocation.license_id == lic.id,
            LicenseAllocation.status.in_(USED_STATUSES)).limit(1)) is not None

    def can_change_product(self, license_id: int) -> bool:
        """A key's product (and so its licence type) may be corrected only while it has never been sold,
        or every sale using it was cancelled with the activations returned to stock."""
        with self.ctx.db.session() as s:
            lic = s.get(License, license_id)
            if not lic:
                raise NotFoundError("Licence not found.")
            return not self._has_used_allocations(s, lic)

    def update_license(self, license_id: int, *, supplier_name: str | None, restrictions: str | None,
                       expiration_date: str | None, notes: str | None, allows_multiple_customers: bool,
                       reassignable: bool, product_id: int | None = None,
                       license_type_id: int | None = None) -> None:
        """Edit a key's details. product_id and/or license_type_id correct a wrong product or licence type;
        this is only allowed while the key has no sold activations."""
        with self.ctx.db.session() as s:
            lic = s.get(License, license_id)
            if not lic:
                raise NotFoundError("Licence not found.")
            if license_type_id is not None:
                current_type = s.get(Product, product_id or lic.product_id).license_type_id
                if license_type_id != current_type:
                    if self._has_used_allocations(s, lic):
                        product_id = -1  # force the "already sold" error below
                    else:
                        from bejitech.services.catalogue_service import CatalogueService
                        product_id = CatalogueService.variant_in_session(
                            s, product_id or lic.product_id, license_type_id, self.ctx.user_id).id
            if product_id is not None and product_id != lic.product_id:
                new_product = s.get(Product, product_id) if product_id > 0 else None
                if self._has_used_allocations(s, lic):
                    raise ValidationError(
                        f"{lic.inventory_ref} has already been sold, so its product or licence type cannot be "
                        "changed (that would alter past sales and delivery notes). Cancel those sales with the "
                        "activations returned to stock first, or disable this key and add it again correctly.")
                if not new_product or new_product.is_archived:
                    raise ValidationError("Please choose an active product.")
                old_name = lic.product.display_name
                lic.product_id = new_product.id
                audit(s, self.ctx.user_id, "PRODUCT_CHANGED", "license", lic.uuid, ref=lic.inventory_ref,
                      from_product=old_name, to_product=new_product.display_name,
                      license_type=new_product.license_type.name)
            try:
                exp = parse_date(clean(expiration_date))
            except ValueError as exc:
                raise ValidationError("Expiry date must be in YYYY-MM-DD format.") from exc
            if allows_multiple_customers is False and lic.allows_multiple_customers:
                customers = s.scalar(select(func.count(func.distinct(LicenseAllocation.customer_id))).where(
                    LicenseAllocation.license_id == lic.id, LicenseAllocation.status.in_(USED_STATUSES)))
                if customers and customers > 1:
                    raise ValidationError("This key is already allocated to several customers.")
            sup = self._supplier(s, supplier_name)
            lic.supplier_id = sup.id if sup else None
            lic.restrictions = clean(restrictions)
            lic.expiration_date = exp.isoformat() if exp else None
            lic.notes = clean(notes)
            lic.allows_multiple_customers = int(allows_multiple_customers)
            lic.reassignable = int(reassignable)
            lic.updated_at = utcnow_iso()
            audit(s, self.ctx.user_id, "UPDATE", "license", lic.uuid, ref=lic.inventory_ref)

    def adjust_capacity(self, license_id: int, new_capacity: int, reason: str) -> None:
        if not clean(reason):
            raise ValidationError("Please give a reason for changing the capacity.")
        with self.ctx.db.session() as s:
            lic = s.get(License, license_id)
            if not lic:
                raise NotFoundError("Licence not found.")
            if new_capacity < max(1, lic.allocated_qty):
                raise ValidationError(
                    f"Capacity cannot be lower than the {lic.allocated_qty} activation(s) already allocated.")
            old = lic.permitted_capacity
            lic.permitted_capacity = new_capacity
            lic.updated_at = utcnow_iso()
            record_event(s, lic, "CAPACITY_ADJUSTED", lic.allocated_qty, self.ctx.user_id,
                         note=f"Capacity {old} → {new_capacity}: {reason.strip()}")
            audit(s, self.ctx.user_id, "UPDATE", "license", lic.uuid, capacity_from=old, capacity_to=new_capacity)

    def set_disabled(self, license_id: int, disabled: bool, reason: str | None = None) -> None:
        with self.ctx.db.session() as s:
            lic = s.get(License, license_id)
            if not lic:
                raise NotFoundError("Licence not found.")
            if disabled and not clean(reason):
                raise ValidationError("Please give a reason for disabling this key.")
            lic.status = LicenseStatus.DISABLED if disabled else LicenseStatus.ACTIVE
            lic.disabled_reason = clean(reason) if disabled else None
            lic.updated_at = utcnow_iso()
            record_event(s, lic, "DISABLED" if disabled else "ENABLED", lic.allocated_qty, self.ctx.user_id,
                         note=clean(reason))
            audit(s, self.ctx.user_id, "DISABLE" if disabled else "ENABLE", "license", lic.uuid)

    # ---------- secrets ----------
    def reveal_key(self, license_id: int, purpose: str = "reveal") -> str:
        """Decrypt a key. Every call is written to the audit log."""
        cipher = self.ctx.require_cipher()
        with self.ctx.db.session() as s:
            lic = s.get(License, license_id)
            if not lic:
                raise NotFoundError("Licence not found.")
            key = cipher.decrypt_license_key(lic.key_ciphertext, lic.key_nonce, lic.uuid)
            audit(s, self.ctx.user_id, "KEY_COPIED" if purpose == "copy" else "KEY_REVEALED",
                  "license", lic.uuid, ref=lic.inventory_ref)
            return key

    # ---------- stock summaries ----------
    def product_stock(self) -> list[dict]:
        with self.ctx.db.session() as s:
            rows = s.execute(text(
                "SELECT product_id, display_name, low_stock_threshold, total_keys, available_activations, "
                "allocated_activations, fully_allocated_keys FROM v_product_stock ORDER BY display_name"))
            return [dict(r._mapping) for r in rows]

    def low_stock_alerts(self) -> list[dict]:
        return [r for r in self.product_stock() if r["available_activations"] < r["low_stock_threshold"]]

    def verify_consistency(self) -> list[str]:
        """Recompute counters from allocation rows and report any mismatch."""
        problems = []
        with self.ctx.db.session() as s:
            for lic in s.scalars(select(License)):
                used = s.scalar(select(func.coalesce(func.sum(LicenseAllocation.quantity), 0)).where(
                    LicenseAllocation.license_id == lic.id, LicenseAllocation.status.in_(USED_STATUSES)))
                confirmed = s.scalar(select(func.coalesce(func.sum(LicenseAllocation.quantity), 0)).where(
                    LicenseAllocation.license_id == lic.id,
                    (LicenseAllocation.status == AllocationStatus.CONFIRMED)
                    | ((LicenseAllocation.status == AllocationStatus.CONSUMED)
                       & LicenseAllocation.confirmed_at.is_not(None))))
                if used != lic.allocated_qty:
                    problems.append(f"{lic.inventory_ref}: allocated counter {lic.allocated_qty}, allocations total {used}")
                if confirmed != lic.confirmed_qty:
                    problems.append(f"{lic.inventory_ref}: confirmed counter {lic.confirmed_qty}, confirmations total {confirmed}")
        return problems
