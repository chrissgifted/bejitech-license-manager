"""SQLAlchemy ORM models. They mirror sql/0001_initial.sql exactly;
tests/integration/test_migrations.py fails if they drift apart."""
from __future__ import annotations

import uuid as _uuid

from sqlalchemy import ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def new_uuid() -> str:
    return str(_uuid.uuid4())


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[str] = mapped_column(String, default=new_uuid, unique=True)
    username: Mapped[str] = mapped_column(String, unique=True)
    display_name: Mapped[str] = mapped_column(String)
    password_hash: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String, default="ADMIN")
    is_active: Mapped[int] = mapped_column(Integer, default=1)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    last_login_at: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String)
    updated_at: Mapped[str] = mapped_column(String)
    # migration 2: two-step login (authenticator secret encrypted with the DEK) and lockout
    totp_secret: Mapped[bytes | None] = mapped_column(LargeBinary)
    totp_nonce: Mapped[bytes | None] = mapped_column(LargeBinary)
    totp_last_step: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[str | None] = mapped_column(String)


class KeyEscrow(Base):
    __tablename__ = "key_escrow"
    id: Mapped[int] = mapped_column(primary_key=True)
    purpose: Mapped[str] = mapped_column(String, unique=True)
    kdf: Mapped[str] = mapped_column(String, default="argon2id")
    kdf_params: Mapped[str] = mapped_column(Text)
    wrapped_key: Mapped[bytes] = mapped_column(LargeBinary)
    nonce: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[str] = mapped_column(String)


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[str] = mapped_column(String)


class ReferenceSequence(Base):
    __tablename__ = "reference_sequences"
    prefix: Mapped[str] = mapped_column(String, primary_key=True)
    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    next_value: Mapped[int] = mapped_column(Integer, default=1)


class ExchangeRate(Base):
    __tablename__ = "exchange_rates"
    id: Mapped[int] = mapped_column(primary_key=True)
    from_currency: Mapped[str] = mapped_column(String)
    to_currency: Mapped[str] = mapped_column(String, default="TZS")
    rate: Mapped[str] = mapped_column(String)
    effective_date: Mapped[str] = mapped_column(String)
    source_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String)


class Publisher(Base):
    __tablename__ = "publishers"
    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[str] = mapped_column(String, default=new_uuid, unique=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    website: Mapped[str | None] = mapped_column(String)
    is_archived: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String)
    updated_at: Mapped[str] = mapped_column(String)


class Category(Base):
    __tablename__ = "categories"
    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[str] = mapped_column(String, default=new_uuid, unique=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class LicenseType(Base):
    __tablename__ = "license_types"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text)
    allows_multiple_customers: Mapped[int] = mapped_column(Integer, default=0)
    reassignable: Mapped[int] = mapped_column(Integer, default=0)
    default_capacity: Mapped[int] = mapped_column(Integer, default=1)


class ProductLine(Base):
    __tablename__ = "product_lines"
    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[str] = mapped_column(String, default=new_uuid, unique=True)
    publisher_id: Mapped[int] = mapped_column(ForeignKey("publishers.id"))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    name: Mapped[str] = mapped_column(String)
    is_archived: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String)
    updated_at: Mapped[str] = mapped_column(String)

    publisher: Mapped[Publisher] = relationship()
    category: Mapped[Category] = relationship()


class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[str] = mapped_column(String, default=new_uuid, unique=True)
    product_line_id: Mapped[int] = mapped_column(ForeignKey("product_lines.id"))
    display_name: Mapped[str] = mapped_column(String)
    version: Mapped[str] = mapped_column(String)
    edition: Mapped[str] = mapped_column(String)
    platform: Mapped[str] = mapped_column(String, default="Windows")
    license_type_id: Mapped[int] = mapped_column(ForeignKey("license_types.id"))
    sku_code: Mapped[str | None] = mapped_column(String)
    logo_path: Mapped[str | None] = mapped_column(String)
    purchase_price_minor: Mapped[int] = mapped_column(Integer, default=0)
    purchase_currency: Mapped[str] = mapped_column(String, default="TZS")
    selling_price_minor: Mapped[int] = mapped_column(Integer, default=0)
    selling_currency: Mapped[str] = mapped_column(String, default="TZS")
    download_url: Mapped[str | None] = mapped_column(String)
    download_label: Mapped[str | None] = mapped_column(String)
    download_url_verified: Mapped[int] = mapped_column(Integer, default=0)
    download_url_verified_at: Mapped[str | None] = mapped_column(String)
    installation_instructions: Mapped[str | None] = mapped_column(Text)
    activation_instructions: Mapped[str | None] = mapped_column(Text)
    low_stock_threshold: Mapped[int] = mapped_column(Integer, default=3)
    is_archived: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String)
    updated_at: Mapped[str] = mapped_column(String)

    product_line: Mapped[ProductLine] = relationship()
    license_type: Mapped[LicenseType] = relationship()


class Supplier(Base):
    __tablename__ = "suppliers"
    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[str] = mapped_column(String, default=new_uuid, unique=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    contact_name: Mapped[str | None] = mapped_column(String)
    phone: Mapped[str | None] = mapped_column(String)
    email: Mapped[str | None] = mapped_column(String)
    website: Mapped[str | None] = mapped_column(String)
    notes: Mapped[str | None] = mapped_column(Text)
    is_archived: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String)
    updated_at: Mapped[str] = mapped_column(String)


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[str] = mapped_column(String, default=new_uuid, unique=True)
    customer_ref: Mapped[str] = mapped_column(String, unique=True)
    full_name: Mapped[str] = mapped_column(String)
    organization: Mapped[str | None] = mapped_column(String)
    phone: Mapped[str | None] = mapped_column(String)
    email: Mapped[str | None] = mapped_column(String)
    address: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    is_archived: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String)
    updated_at: Mapped[str] = mapped_column(String)


class License(Base):
    __tablename__ = "licenses"
    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[str] = mapped_column(String, default=new_uuid, unique=True)
    inventory_ref: Mapped[str] = mapped_column(String, unique=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"))
    key_ciphertext: Mapped[bytes] = mapped_column(LargeBinary)
    key_nonce: Mapped[bytes] = mapped_column(LargeBinary)
    key_suffix: Mapped[str] = mapped_column(String)
    key_fingerprint: Mapped[str] = mapped_column(String, unique=True)
    purchase_date: Mapped[str] = mapped_column(String)
    purchase_cost_minor: Mapped[int] = mapped_column(Integer)
    purchase_currency: Mapped[str] = mapped_column(String, default="TZS")
    exchange_rate_to_tzs: Mapped[str] = mapped_column(String, default="1")
    purchase_cost_tzs: Mapped[int] = mapped_column(Integer)
    permitted_capacity: Mapped[int] = mapped_column(Integer)
    allocated_qty: Mapped[int] = mapped_column(Integer, default=0)
    confirmed_qty: Mapped[int] = mapped_column(Integer, default=0)
    allows_multiple_customers: Mapped[int] = mapped_column(Integer, default=0)
    reassignable: Mapped[int] = mapped_column(Integer, default=0)
    restrictions: Mapped[str | None] = mapped_column(Text)
    expiration_date: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="ACTIVE")
    disabled_reason: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String)
    updated_at: Mapped[str] = mapped_column(String)

    product: Mapped[Product] = relationship()
    supplier: Mapped[Supplier | None] = relationship()


class Sale(Base):
    __tablename__ = "sales"
    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[str] = mapped_column(String, default=new_uuid, unique=True)
    sales_ref: Mapped[str] = mapped_column(String, unique=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    sale_date: Mapped[str] = mapped_column(String)
    currency: Mapped[str] = mapped_column(String, default="TZS")
    subtotal_minor: Mapped[int] = mapped_column(Integer)
    discount_minor: Mapped[int] = mapped_column(Integer, default=0)
    total_minor: Mapped[int] = mapped_column(Integer)
    payment_method: Mapped[str] = mapped_column(String)
    payment_reference: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="COMPLETED")
    cancelled_at: Mapped[str | None] = mapped_column(String)
    cancel_reason: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[str] = mapped_column(String)
    updated_at: Mapped[str] = mapped_column(String)

    customer: Mapped[Customer] = relationship()
    items: Mapped[list["SaleItem"]] = relationship(back_populates="sale", order_by="SaleItem.id")


class SaleItem(Base):
    __tablename__ = "sale_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[str] = mapped_column(String, default=new_uuid, unique=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price_minor: Mapped[int] = mapped_column(Integer)
    discount_minor: Mapped[int] = mapped_column(Integer, default=0)
    line_total_minor: Mapped[int] = mapped_column(Integer)

    sale: Mapped[Sale] = relationship(back_populates="items")
    product: Mapped[Product] = relationship()
    allocations: Mapped[list["LicenseAllocation"]] = relationship(
        back_populates="sale_item", order_by="LicenseAllocation.id"
    )


class LicenseAllocation(Base):
    __tablename__ = "license_allocations"
    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[str] = mapped_column(String, default=new_uuid, unique=True)
    license_id: Mapped[int] = mapped_column(ForeignKey("licenses.id"))
    sale_item_id: Mapped[int] = mapped_column(ForeignKey("sale_items.id"))
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_cost_tzs: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String, default="ALLOCATED")
    allocated_at: Mapped[str] = mapped_column(String)
    confirmed_at: Mapped[str | None] = mapped_column(String)
    closed_at: Mapped[str | None] = mapped_column(String)
    close_reason: Mapped[str | None] = mapped_column(Text)

    license: Mapped[License] = relationship()
    sale_item: Mapped[SaleItem] = relationship(back_populates="allocations")
    customer: Mapped[Customer] = relationship()


class AllocationEvent(Base):
    __tablename__ = "allocation_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    license_id: Mapped[int] = mapped_column(ForeignKey("licenses.id"))
    allocation_id: Mapped[int | None] = mapped_column(ForeignKey("license_allocations.id"))
    event_type: Mapped[str] = mapped_column(String)
    qty_delta: Mapped[int] = mapped_column(Integer, default=0)
    allocated_before: Mapped[int] = mapped_column(Integer)
    allocated_after: Mapped[int] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(Text)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[str] = mapped_column(String)

    allocation: Mapped[LicenseAllocation | None] = relationship()


class DeliveryNote(Base):
    __tablename__ = "delivery_notes"
    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[str] = mapped_column(String, default=new_uuid, unique=True)
    note_number: Mapped[str] = mapped_column(String, unique=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.id"))
    revision: Mapped[int] = mapped_column(Integer, default=1)
    delivery_date: Mapped[str] = mapped_column(String)
    seller_snapshot: Mapped[str] = mapped_column(Text)
    customer_snapshot: Mapped[str] = mapped_column(Text)
    include_signature: Mapped[int] = mapped_column(Integer, default=1)
    pdf_path: Mapped[str | None] = mapped_column(String)
    pdf_sha256: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="ISSUED")
    void_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String)

    sale: Mapped[Sale] = relationship()


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    occurred_at: Mapped[str] = mapped_column(String)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String)
    entity_type: Mapped[str | None] = mapped_column(String)
    entity_uuid: Mapped[str | None] = mapped_column(String)
    details: Mapped[str | None] = mapped_column(Text)


class BackupHistory(Base):
    __tablename__ = "backup_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[str] = mapped_column(String, default=new_uuid, unique=True)
    kind: Mapped[str] = mapped_column(String)
    file_path: Mapped[str] = mapped_column(String)
    file_sha256: Mapped[str] = mapped_column(String)
    size_bytes: Mapped[int] = mapped_column(Integer)
    schema_revision: Mapped[str] = mapped_column(String)
    app_version: Mapped[str] = mapped_column(String)
    verified: Mapped[int] = mapped_column(Integer, default=0)
    verified_at: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String)
