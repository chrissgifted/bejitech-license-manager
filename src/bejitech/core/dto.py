"""Plain data objects passed between the UI and the services (no Qt, no ORM)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ProductInput:
    publisher_name: str
    category_name: str
    product_line_name: str
    version: str
    edition: str
    license_type_id: int
    platform: str = "Windows"
    display_name: str = ""
    sku_code: str | None = None
    purchase_price_minor: int = 0
    purchase_currency: str = "TZS"
    selling_price_minor: int = 0
    download_url: str | None = None
    download_label: str | None = None
    download_url_verified: bool = False
    installation_instructions: str | None = None
    activation_instructions: str | None = None
    low_stock_threshold: int = 3
    id: int | None = None


@dataclass
class ProductRow:
    id: int
    uuid: str
    display_name: str
    publisher: str
    category: str
    product_line: str
    version: str
    edition: str
    platform: str
    license_type: str
    license_type_id: int
    selling_price_minor: int
    purchase_price_minor: int
    purchase_currency: str
    logo_path: str | None
    download_url: str | None
    download_label: str | None
    download_url_verified: bool
    installation_instructions: str | None
    activation_instructions: str | None
    low_stock_threshold: int
    sku_code: str | None
    is_archived: bool
    total_keys: int = 0
    available_activations: int = 0
    allocated_activations: int = 0

    @property
    def effective_download_label(self) -> str:
        return (self.download_label or "").strip() or f"Download {self.display_name}"

    @property
    def is_low_stock(self) -> bool:
        return not self.is_archived and self.available_activations < self.low_stock_threshold


@dataclass
class LicenseInput:
    product_id: int
    license_key: str
    purchase_date: str
    purchase_cost_minor: int
    permitted_capacity: int
    purchase_currency: str = "TZS"
    exchange_rate_to_tzs: str = "1"
    supplier_name: str | None = None
    allows_multiple_customers: bool | None = None  # None → licence-type default
    reassignable: bool | None = None
    restrictions: str | None = None
    expiration_date: str | None = None
    notes: str | None = None


@dataclass
class LicenseRow:
    id: int
    uuid: str
    inventory_ref: str
    product_id: int
    product_name: str
    supplier: str | None
    masked_key: str
    key_suffix: str
    permitted_capacity: int
    allocated_qty: int
    confirmed_qty: int
    remaining_qty: int
    stock_state: str
    status: str
    purchase_date: str
    purchase_cost_minor: int
    purchase_currency: str
    exchange_rate_to_tzs: str
    purchase_cost_tzs: int
    allows_multiple_customers: bool
    reassignable: bool
    restrictions: str | None
    expiration_date: str | None
    notes: str | None
    disabled_reason: str | None = None


@dataclass
class HistoryRow:
    created_at: str
    event_type: str
    qty_delta: int
    allocated_before: int
    allocated_after: int
    customer: str | None
    sales_ref: str | None
    note: str | None


@dataclass
class AllocationOption:
    license_id: int
    inventory_ref: str
    masked_key: str
    remaining: int
    take: int
    expiration_date: str | None
    reason: str = ""


@dataclass
class Recommendation:
    product_id: int
    quantity: int
    total_available: int
    plan: list[AllocationOption] = field(default_factory=list)  # recommended allocation
    alternatives: list[AllocationOption] = field(default_factory=list)  # other single keys
    shortfall: int = 0

    @property
    def is_possible(self) -> bool:
        return self.shortfall == 0 and bool(self.plan)


@dataclass
class CustomerInput:
    full_name: str
    organization: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    notes: str | None = None
    id: int | None = None


@dataclass
class CustomerRow:
    id: int
    uuid: str
    customer_ref: str
    full_name: str
    organization: str | None
    phone: str | None
    email: str | None
    address: str | None
    notes: str | None
    is_archived: bool
    purchases: int = 0
    total_spent_minor: int = 0

    @property
    def label(self) -> str:
        parts = [self.full_name]
        if self.organization:
            parts.append(self.organization)
        if self.phone:
            parts.append(self.phone)
        return " · ".join(parts)


@dataclass
class SaleInput:
    customer_id: int
    product_id: int
    quantity: int
    unit_price_minor: int
    payment_method: str
    sale_date: str
    discount_minor: int = 0
    payment_reference: str | None = None
    notes: str | None = None
    plan: list[tuple[int, int]] | None = None  # [(license_id, qty)], None → recommended


@dataclass
class AllocationView:
    id: int
    license_id: int
    inventory_ref: str
    masked_key: str
    quantity: int
    status: str
    unit_cost_tzs: int
    confirmed_at: str | None


@dataclass
class SaleRow:
    id: int
    uuid: str
    sales_ref: str
    sale_date: str
    customer_id: int
    customer_name: str
    product_names: str
    quantity: int
    subtotal_minor: int
    discount_minor: int
    total_minor: int
    payment_method: str
    payment_reference: str | None
    status: str
    cancel_reason: str | None
    notes: str | None
    delivery_note_id: int | None = None
    delivery_note_number: str | None = None
    allocations: list[AllocationView] = field(default_factory=list)


@dataclass
class CancelOption:
    allocation_id: int
    inventory_ref: str
    masked_key: str
    quantity: int
    status: str
    can_release: bool
    reason: str


@dataclass
class DeliveryNoteRow:
    id: int
    note_number: str
    sale_id: int
    sales_ref: str
    customer_name: str
    customer_email: str | None
    delivery_date: str
    status: str
    pdf_path: str | None
    revision: int


@dataclass
class Report:
    title: str
    subtitle: str
    headers: list[str]
    rows: list[list]
    totals: list | None = None
