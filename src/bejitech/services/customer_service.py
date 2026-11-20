from __future__ import annotations

import re

from sqlalchemy import func, select

from bejitech.core.dto import CustomerInput, CustomerRow, SaleRow
from bejitech.core.enums import SaleStatus
from bejitech.core.errors import NotFoundError, ValidationError
from bejitech.core.timeutil import utcnow_iso
from bejitech.db.models import Customer, Sale
from bejitech.services.common import audit, clean, next_reference

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class CustomerService:
    def __init__(self, ctx):
        self.ctx = ctx

    def save(self, data: CustomerInput) -> int:
        name = (data.full_name or "").strip()
        if not name:
            raise ValidationError("Customer name is required.")
        email = clean(data.email)
        if email and not _EMAIL.match(email):
            raise ValidationError("That email address does not look valid.")
        with self.ctx.db.session() as s:
            now = utcnow_iso()
            if data.id:
                c = s.get(Customer, data.id)
                if not c:
                    raise NotFoundError("Customer not found.")
                action = "UPDATE"
            else:
                c = Customer(customer_ref=next_reference(s, "CUS"), created_at=now)
                s.add(c)
                action = "CREATE"
            c.full_name = name
            c.organization = clean(data.organization)
            c.phone = clean(data.phone)
            c.email = email
            c.address = clean(data.address)
            c.notes = clean(data.notes)
            c.updated_at = now
            s.flush()
            audit(s, self.ctx.user_id, action, "customer", c.uuid, ref=c.customer_ref)
            return c.id

    def set_archived(self, customer_id: int, archived: bool) -> None:
        with self.ctx.db.session() as s:
            c = s.get(Customer, customer_id)
            if not c:
                raise NotFoundError("Customer not found.")
            c.is_archived = int(archived)
            c.updated_at = utcnow_iso()
            audit(s, self.ctx.user_id, "ARCHIVE" if archived else "UNARCHIVE", "customer", c.uuid)

    def list(self, search: str = "", include_archived: bool = False) -> list[CustomerRow]:
        with self.ctx.db.session() as s:
            stats = select(Sale.customer_id, func.count(Sale.id).label("n"),
                           func.coalesce(func.sum(Sale.total_minor), 0).label("total")) \
                .where(Sale.status == SaleStatus.COMPLETED).group_by(Sale.customer_id).subquery()
            q = select(Customer, stats.c.n, stats.c.total).outerjoin(stats, stats.c.customer_id == Customer.id)
            if not include_archived:
                q = q.where(Customer.is_archived == 0)
            if search:
                like = f"%{search.strip()}%"
                q = q.where(Customer.full_name.ilike(like) | Customer.organization.ilike(like)
                            | Customer.phone.ilike(like) | Customer.email.ilike(like)
                            | Customer.customer_ref.ilike(like))
            q = q.order_by(Customer.full_name)
            return [self._row(c, n or 0, t or 0) for c, n, t in s.execute(q)]

    @staticmethod
    def _row(c: Customer, n: int = 0, total: int = 0) -> CustomerRow:
        return CustomerRow(c.id, c.uuid, c.customer_ref, c.full_name, c.organization, c.phone, c.email,
                           c.address, c.notes, bool(c.is_archived), n, total)

    def get(self, customer_id: int) -> CustomerRow:
        for row in self.list(include_archived=True):
            if row.id == customer_id:
                return row
        raise NotFoundError("Customer not found.")

    def history(self, customer_id: int) -> list[SaleRow]:
        return self.ctx.sales.list_sales(customer_id=customer_id)
