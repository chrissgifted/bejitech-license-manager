# Bejitech License Manager: Database Schema (v1)

Phase 1 deliverable · Full SQL: [`db/schema_v1.sql`](../db/schema_v1.sql)

The application will create this schema through SQLAlchemy models and migration `0001_initial` (built-in runner). The SQL file is the human-reviewable reference.

## 1. Entity relationship overview

```
publishers ─┐
            ├─< product_lines >── categories
            │        │
            │        └─< products >── license_types
            │                │
suppliers ──┼──────< licenses (encrypted key, capacity, allocated)
            │                │
            │                ├─< license_allocations >── sale_items >── sales >── customers
            │                │            │                                 │
            │                └─< allocation_events (append-only)            └─< delivery_notes
            │
users ── audit_log (append-only) · backup_history · settings · key_escrow
         reference_sequences · exchange_rates
```

`A ─< B` means one A has many B.

## 2. Tables (20)

| Group | Table | Purpose |
|-------|-------|---------|
| Admin | `users` | Administrator login (Argon2id hash) |
| | `key_escrow` | Encryption key wrapped by recovery passphrase |
| | `settings` | Seller name/phone/email, defaults, thresholds (key/value) |
| | `reference_sequences` | Gap-free yearly counters for INV/SAL/DN/CUS numbers |
| | `exchange_rates` | USD→TZS rate history |
| Catalogue | `publishers` | Microsoft, Adobe, Corel, ESET… |
| | `categories` | Office Suites, Operating Systems, Servers, Design, Security… |
| | `license_types` | Retail, OEM, MAK, Volume, Subscription, Bind, with default rules for multi-customer and reassignment |
| | `product_lines` | Product family under a publisher ("Microsoft Office") |
| | `products` | **Sellable item**: version + edition + platform + licence type, prices, logo, download URL + label, instructions, low-stock threshold |
| Parties | `suppliers` | Where keys were bought |
| | `customers` | Name, organisation, phone, email |
| Inventory | `licenses` | One purchased key: encrypted key, cost, capacity, allocated, confirmed, restrictions, expiry, status |
| Sales | `sales` | Sale header: ref, customer, date, subtotal, discount, total, payment |
| | `sale_items` | Product, quantity, unit price, line discount, line total |
| | `license_allocations` | Which key, how many activations, to which customer; ALLOCATED → CONFIRMED / RELEASED / CONSUMED; cost snapshot |
| | `allocation_events` | Append-only history of every capacity change |
| Documents | `delivery_notes` | DN number, sale link, snapshots of seller/customer, PDF path + hash, revision, ISSUED/VOID |
| Audit | `audit_log` | Append-only security and business event log |
| | `backup_history` | Every backup, its hash and verification result |

Plus two **views**: `v_license_stock` (remaining activations and stock state per key) and `v_product_stock` (totals per product for dashboard and low-stock alerts).

## 3. How the spec's fields map to the schema

**Product (spec section 3)**: name → `products.display_name`; publisher → `product_lines.publisher_id`; category → `product_lines.category_id`; version, edition, platform → `products.*`; licence type → `products.license_type_id`; logo → `products.logo_path`; purchase/selling prices → `products.purchase_price_minor` / `selling_price_minor`; download URL + friendly label → `download_url` / `download_label`; installation and activation instructions → own columns; archive → `is_archived`.

**Licence (spec section 4)**: unique inventory reference → `inventory_ref`; product → `product_id`; key → `key_ciphertext` + `key_nonce` (+ `key_suffix`, `key_fingerprint`); supplier, purchase date, cost, currency → own columns (+ `exchange_rate_to_tzs`, `purchase_cost_tzs`); permitted capacity → `permitted_capacity`; allocated → `allocated_qty`; remaining → **calculated** in `v_license_stock`; restrictions, expiry, notes, status → own columns. The five display states (available, partially allocated, fully allocated, expired, disabled) are derived in `v_license_stock.stock_state`.

**Sale (spec section 6)**: sales reference, customer, payment method, date → `sales`; product, quantity, unit price, discount, total → `sale_items` + `sales` totals; licence allocation → `license_allocations`; delivery note reference → `delivery_notes.sale_id`.

## 4. Integrity rules enforced by the database itself

These are a second safety net behind the service layer:

| Rule | Mechanism |
|------|-----------|
| No overselling | `CHECK (allocated_qty <= permitted_capacity)` on `licenses` |
| Confirmed never exceeds allocated | `CHECK (confirmed_qty <= allocated_qty)` |
| Same key can't be entered twice | `UNIQUE (key_fingerprint)` |
| Sale totals consistent | `CHECK (total = subtotal − discount)`, `CHECK (line_total = qty × unit_price − discount)` |
| History can't be altered | Triggers block `UPDATE`/`DELETE` on `allocation_events` and `audit_log` |
| No orphan records | Foreign keys (`PRAGMA foreign_keys = ON` on every connection) |
| No negative money/quantities | `CHECK (… >= 0)` / `>= 1` |

**Verified in SQLite 3.53 during Phase 1** with [`db/check_schema.py`](../db/check_schema.py): schema loads; remaining-activation view correct; oversell, duplicate key, wrong sale total and broken foreign key are all rejected; append-only trigger works. (This is a schema check only. The application code does not exist yet.)

## 5. Design notes

- **Integer money.** `*_minor` columns are integers: whole shillings for TZS, cents for USD. No floating-point rounding errors.
- **Cost snapshots.** `licenses.purchase_cost_tzs` freezes the TZS cost using the rate on purchase day; `license_allocations.unit_cost_tzs` freezes cost per activation at sale time. Profit reports never shift when rates or prices change later.
- **Snapshots on delivery notes.** Seller and customer details are copied as JSON when a note is issued, so changing your phone number in Settings next year does not alter old notes. Regenerating creates a new `revision`.
- **Nothing is hard-deleted.** Products, customers and suppliers are archived; licences are disabled; sales are cancelled. This keeps history and reports correct.
- **Allocated `allocated_qty` is a maintained counter**, updated in the same transaction as each allocation row. A consistency test (and a "Verify inventory" tool in Phase 6) recomputes it from `license_allocations` and flags any mismatch.
- **PostgreSQL-ready.** Only portable types and constructs; UUIDs for identity; UTC ISO timestamps. Views and triggers will be re-expressed in the PostgreSQL migration.

## 6. Seed data (inserted in Phase 2 by migration)

| Table | Rows |
|-------|------|
| publishers | Microsoft |
| categories | Office Suites, Operating Systems, Servers, Developer Tools, Design & Graphics, Security, Other |
| license_types | RETAIL, OEM, MAK, VOLUME, SUBSCRIPTION, BIND (all with multi-customer **off** by default; you can change them in Settings) |
| product_lines | Microsoft Office, Windows |
| products | Office 2019 Professional Plus · Office 2021 Professional Plus · Office 2024 Professional Plus · Windows 11 Pro (prices 0 until you set them; neutral placeholder logos; download URLs left for you to confirm) |
| settings | `seller.name = Christian Joel Mtei`, `seller.phone = ""`, `seller.email = ""`, `currency.default = TZS` |
