# Bejitech License Manager: Architecture Document

Phase 1 deliverable · Version 1.0 · 18 November 2026 · Status: **awaiting approval**

---

## 1. Understanding of the application

Bejitech License Manager is an offline macOS desktop application for Christian Joel Mtei's digital software licence business. It replaces spreadsheets and manual notes with one secure system that answers four everyday questions:

1. **What do I sell?** A catalogue of software products (Office 2019/2021/2024 Pro Plus, Windows 11 Pro, and any number of future products), organised as Publisher → Product → Version → Edition → License Type, with prices, logos, download links and instructions.
2. **What do I have in stock?** Every purchased licence key, its supplier and cost, how many activations it permits, how many are already allocated, and how many remain.
3. **Who bought what?** Customers, sales, discounts, payment methods, and which key (and how many activations of it) went to which customer.
4. **What does the customer receive?** A premium, product-branded A4 PDF delivery note containing the key, activation count, a clickable friendly download link, and installation/activation instructions.

### Core business rules (these drive the design)

| # | Rule | How the design enforces it |
|---|------|----------------------------|
| R1 | Remaining = Permitted capacity − Allocated | `allocated_qty` is maintained in the same transaction as each allocation; remaining is derived, never typed in |
| R2 | Never oversell | Service-layer check **and** a database `CHECK (allocated_qty <= permitted_capacity)` so a bug cannot bypass it |
| R3 | Allocations are atomic | One SQLite transaction (`BEGIN IMMEDIATE`) covers sale + sale item + allocation + inventory update + history + audit. Any failure rolls back everything |
| R4 | Allocated ≠ confirmed | Each allocation has status `ALLOCATED` → `CONFIRMED` (customer reports successful activation) |
| R5 | Cancellations don't blindly restore stock | Cancelling a sale asks per allocation: *release* (returns capacity) only if not confirmed and the licence type allows reassignment; otherwise it is marked `CONSUMED` and capacity stays used |
| R6 | Multi-customer allocation only when terms allow | Licence types carry `allows_multiple_customers` / `reassignable` defaults; each licence can override. Allocation service refuses a second customer on a single-customer key |
| R7 | Full allocation history | Append-only `allocation_events` table; rows are never updated or deleted |
| R8 | Keys are secret | Encrypted at rest (AES-256-GCM), masked in the UI, revealed/copied only by explicit action, every reveal/copy audited |
| R9 | TZS first | Default currency TZS; USD purchase cost allowed with a recorded exchange rate; all reports in TZS |

### Explicitly out of scope for release 1

Website, cloud server, mobile app, multi-user roles, online payments, automatic email sending with attachments. The architecture leaves room for each (section 8).

---

## 2. Architecture overview

A **layered architecture** with strict one-way dependencies. The UI never touches the database directly; business rules live in plain Python services that can later sit behind a web API unchanged.

```
┌──────────────────────────────────────────────────────────────┐
│  PRESENTATION  (PySide6)                                      │
│  MainWindow · Sidebar · Views · Dialogs · Table models        │
│  Only talks to services. No SQL, no crypto.                   │
└───────────────────────────┬──────────────────────────────────┘
                            │ calls (DTOs in / DTOs out)
┌───────────────────────────▼──────────────────────────────────┐
│  APPLICATION SERVICES  (pure Python, no Qt imports)          │
│  CatalogueService · InventoryService · AllocationService     │
│  SalesService · CustomerService · DeliveryNoteService        │
│  ReportingService · BackupService · AuthService ·            │
│  AuditService · SettingsService                              │
│  Own transactions, enforce business rules R1–R9.             │
└──────┬───────────────────┬───────────────────┬───────────────┘
       │                   │                   │
┌──────▼──────┐   ┌────────▼────────┐  ┌───────▼────────────────┐
│ PERSISTENCE │   │ SECURITY        │  │ DOCUMENTS              │
│ SQLAlchemy  │   │ crypto (AES-GCM)│  │ ReportLab PDF builders │
│ ORM models, │   │ keystore        │  │ delivery note, reports │
│ repositories│   │ (macOS Keychain)│  │ CSV exporters          │
│ migrations  │   │ Argon2id hashing│  │                        │
└──────┬──────┘   └─────────────────┘  └────────────────────────┘
       │
┌──────▼──────────────────────────────────────────────────────┐
│  SQLite file in ~/Library/Application Support/...           │
└─────────────────────────────────────────────────────────────┘
```

### Layer responsibilities

| Layer | Package | Responsibility | May import |
|-------|---------|----------------|------------|
| Presentation | `bejitech.ui` | Windows, forms, tables, validation feedback, threading for slow tasks (PDF, backup) | services, core |
| Services | `bejitech.services` | Use cases and business rules; transaction boundaries; audit calls | db, security, pdf, core |
| Core / domain | `bejitech.core` | Enums, DTO dataclasses, money type, error types, reference-number formats | nothing internal |
| Persistence | `bejitech.db` | Engine/session, ORM models, repositories, migrations | core |
| Security | `bejitech.security` | Encryption, key management, password hashing | core |
| Documents | `bejitech.pdf`, `bejitech.exports` | PDF and CSV generation from DTOs | core |
| Config | `bejitech.config` | OS-specific paths, app settings loading | core |

**Why this matters for the future:** Phase 9/10 (iPhone, online store) need a server. Because services take and return plain dataclasses and contain no Qt code, the same services can be wrapped by a FastAPI layer later. The desktop app then either keeps its local DB or becomes a client of that API.

### Key runtime flows

**A. New sale (smart allocation), one atomic transaction**

```
UI: pick customer → pick product → qty
        │
        ▼
AllocationService.recommend(product_id, qty, customer_id)
   1. candidate licences = same product, status ACTIVE, not expired,
      remaining > 0, (multi-customer allowed OR no other customer yet)
   2. rank: (a) one key covers the whole qty
            (b) expiring soonest first
            (c) partially-used keys before untouched keys (fill first)
            (d) oldest purchase date (FIFO)
   3. return ranked list with remaining capacity per key
        │
UI shows recommendation; seller accepts or picks another key
        ▼
SalesService.create_sale(...)   ── BEGIN IMMEDIATE ──
   • re-read licence rows inside the transaction (no stale data)
   • verify remaining >= qty, multi-customer rule, not expired
   • insert sale, sale_item, license_allocation(s)
   • UPDATE licenses SET allocated_qty = allocated_qty + qty
     (DB CHECK rejects any oversell)
   • insert allocation_events + audit_log
   • reserve delivery-note number
   ── COMMIT ──  (any exception → ROLLBACK, nothing changes)
        ▼
DeliveryNoteService.generate(sale_id) → PDF file + SHA-256 stored
```

**B. Cancellation**

```
SalesService.cancel_sale(sale_id, reason)
  for each allocation:
     if status == CONFIRMED or licence not reassignable → CONSUMED
         (capacity stays used, recorded in history)
     else seller chooses RELEASE → allocated_qty -= qty
  sale.status = CANCELLED, delivery note → VOID
  all in one transaction, audited
```

**C. Revealing a key**

```
UI "Reveal" → AuthService.require_recent_auth() (re-enter password if
idle > N minutes) → InventoryService.reveal_key(id) → decrypt in memory →
show for 30 s / copy to clipboard (auto-clear clipboard after 60 s) →
audit_log(KEY_REVEALED / KEY_COPIED)
```

---

## 3. Security design

### 3.1 Authentication
- Single administrator account created on first launch (no default password in code).
- Password hashed with **Argon2id** (`argon2-cffi`, parameters: time_cost 3, memory 64 MiB, parallelism 4; re-tuned in Phase 6 to ~0.5 s on an M1).
- Lock screen after configurable idle timeout (default 15 min). Failed-login back-off (exponential delay after 5 failures).

### 3.2 License key encryption (envelope encryption)
- A random 256-bit **Data Encryption Key (DEK)** is generated on first run.
- DEK stored in the **macOS Keychain** via `keyring` (service `com.bejitech.licensemanager`). It never touches the SQLite file or source code.
- Each licence key is encrypted with **AES-256-GCM** (`cryptography` library): random 96-bit nonce per record; the record's UUID is used as associated data so a ciphertext cannot be swapped onto another row undetected.
- Stored per key: `key_ciphertext`, `key_nonce`, `key_suffix` (for masked display `XXXXX-XXXXX-XXXXX-XXXXX-7HQ2D`), and `key_fingerprint` = HMAC-SHA256(key, separate HMAC key) to detect duplicate keys without decrypting everything.
- **Recovery:** at first run the admin also sets a *recovery passphrase*. A copy of the DEK is wrapped with a key derived from it (Argon2id KDF) and stored in the database (`key_escrow` table). If the Keychain item is lost (new Mac, reinstall), the passphrase restores access. Without either, encrypted keys are unrecoverable by design. This is stated clearly in the UI.

### 3.3 Backups
- Backup = consistent SQLite snapshot (SQLite online backup API) + logos + delivery-note PDFs + manifest, zipped, then encrypted with AES-256-GCM using a key derived (Argon2id) from a **backup password** chosen at backup time.
- Manifest holds SHA-256 of every file, app version, schema revision, and the wrapped DEK, so a backup restores on a different Mac.
- **Verification:** after writing, the backup is re-opened, decrypted, hashes checked, and `PRAGMA integrity_check` run on the extracted DB. Result recorded in `backup_history`.
- **Restore:** always takes an automatic safety backup of the current data first; refuses backups with a newer schema than the app; runs migrations on older ones.

### 3.4 Other controls
- Audit trail (`audit_log`) for logins, key reveal/copy, create/update/archive, sales, cancellations, backups, restores, settings changes.
- Confirmation dialogs for destructive actions (cancel sale, disable licence, restore, archive); typed confirmation for restore.
- Data lives in `~/Library/Application Support/Bejitech License Manager/`, folder permissions `0700`.
- No secrets in source code or logs; log files redact anything that looks like a licence key.
- Clipboard auto-clear after copying a key.

---

## 4. Data storage locations

| Item | macOS path | Windows path (Phase 8) |
|------|------------|------------------------|
| Database | `~/Library/Application Support/Bejitech License Manager/bejitech.db` | `%APPDATA%\Bejitech\License Manager\bejitech.db` |
| Product logos | `…/logos/<product-uuid>.png` | same structure |
| Delivery notes | `…/delivery_notes/2026/DN-2026-00001.pdf` | same |
| Automatic backups | `…/backups/` (user can choose another folder, e.g. iCloud Drive or an external disk) | same |
| Logs | `~/Library/Logs/Bejitech License Manager/` | `%LOCALAPPDATA%\…\Logs` |
| Encryption key | macOS Keychain | Windows Credential Manager (same `keyring` API) |

Paths are resolved by one module (`bejitech.config.paths`) using `platformdirs`, so Windows support needs no changes elsewhere.

---

## 5. Money, numbers and references

- **Money is stored as integers in minor units** (never floats). TZS is stored in whole shillings (TZS has no cents in practice); USD in cents. Every amount column has a matching currency column.
- **Exchange rates** stored as text decimals (e.g. `"2650.000000"`), handled with Python `Decimal`. Each USD purchase stores the rate used, so historical profit never changes when today's rate changes.
- **Cost of goods sold:** cost per activation = licence cost in TZS ÷ permitted capacity. Snapshot onto each allocation at sale time → gross profit = revenue − Σ allocation costs.
- **Human-readable references** (configurable prefix, yearly counter, gap-free per year):
  - Inventory: `INV-2026-00001`
  - Sale: `SAL-2026-00001`
  - Delivery note: `DN-2026-00001`
  - Customer: `CUS-00001`
- **Stable identifiers:** every business table has an integer primary key (fast locally) **and** a UUID (`uuid` column) that never changes. UUIDs are what a future server, sync engine or PostgreSQL migration uses.

---

## 6. Technology choices and dependencies

| Need | Choice | Notes |
|------|--------|-------|
| Language | Python 3.13 (3.12 also fine) | Native arm64 wheels for all deps on Apple Silicon |
| GUI | PySide6 6.12 | Official Qt for Python, LGPL, native arm64 wheels |
| ORM | SQLAlchemy 2.1 | Typed ORM; same models work on PostgreSQL |
| Migrations | Built-in runner (`db/migrations.py`) | Changed from Alembic during Phase 2: bundles reliably with PyInstaller, no extra dependency, backs up the DB before upgrading |
| PDF | ReportLab 5.x | Pulls in Pillow for logo images |
| Encryption | `cryptography` (AES-GCM, HMAC) | Audited, standard |
| Password hashing / KDF | `argon2-cffi` | Argon2id |
| Keychain | `keyring` | macOS Keychain now, Windows Credential Manager later |
| OS paths | `platformdirs` | Small, removes OS `if` statements |
| Tests | pytest, pytest-qt, pytest-cov | pytest-qt for UI smoke tests |
| Packaging | PyInstaller 6.22+ | Builds `.app`; `.dmg` via `hdiutil` (built into macOS) |

Not used on purpose: web frameworks, cloud SDKs, heavy charting libraries (dashboard charts use Qt's own QtCharts module, which ships with PySide6).

Exact pinned versions are fixed at the start of Phase 2 in `requirements.txt`.

---

## 7. Technical risks and mitigations

| # | Risk | Impact | Mitigation |
|---|------|--------|------------|
| 1 | **Keychain + unsigned app**: macOS ties Keychain access to the app's code signature. Each unsigned rebuild may trigger "allow access" prompts | Annoying prompts; in rare cases key appears missing | Ad-hoc sign builds; recovery passphrase (3.2); document "Always Allow"; recommend Developer ID signing for production |
| 2 | **Gatekeeper**: unsigned/unnotarized `.app` is blocked on first open | User can't open app normally | Document right-click → Open / System Settings → Privacy & Security; document notarization path (Apple Developer Program, US$99/yr) |
| 3 | **Losing the encryption key** (no Keychain item and forgotten recovery passphrase) | Licence keys permanently unreadable | Recovery passphrase at setup, recovery kit PDF, warning in Backup screen, backups carry the wrapped DEK |
| 4 | **Testing limits of my environment**: I work in a Linux container, not on a Mac | macOS-only parts (Keychain, `.app`, Retina rendering, printing dialog) can't be verified by me | Business logic + PDF + offscreen Qt tests run in my environment; every macOS-specific item is marked "requires user-side testing" in the progress file |
| 5 | **App size**: PySide6 bundles are large (~150–250 MB) | Large download | Exclude unused Qt modules in the PyInstaller spec |
| 6 | **SQLite schema changes**: SQLite's ALTER TABLE is limited | Migration failures | Table-rebuild migrations where needed; automatic pre-migration backup; migration tests on a copy of real data |
| 7 | **Concurrent edits / double-click on "Complete sale"** | Duplicate sale or double allocation | `BEGIN IMMEDIATE`, re-check inside transaction, button disabled while saving, unique constraints |
| 8 | **Trademarked logos** | Legal risk if bundled | App ships with neutral placeholder icons; administrator uploads approved logos |
| 9 | **Unverified download links** | Customer gets malware or wrong file | Each URL has a `verified` flag and date; unverified links show a warning in the product form and before generating a PDF |
| 10 | **Licence-term compliance** (e.g. one key to several customers) | Legal/reputational | Per licence-type and per licence `allows_multiple_customers` flag, default **off**; enforced in the allocation service |
| 11 | **Email attachments** | `mailto:` cannot attach files | Phase 5 opens a prepared email (subject/body) and reveals the PDF in Finder; the app will say so plainly. Apple Mail scripting is a possible later enhancement |

---

## 8. Future upgrade path (not built in release 1)

| Phase | What changes | What stays |
|-------|-------------|------------|
| 8 Windows | Packaging (PyInstaller on Windows, MSI/Inno Setup), Credential Manager via same `keyring` API, font tweaks | All services, DB, PDF code |
| 9 iPhone | New FastAPI server on PostgreSQL wrapping the same services; desktop syncs or becomes a client; iPhone gets a mobile web app (PWA) or native app | Business rules, schema shape, UUIDs |
| 10 Online store | Storefront, customer accounts, payment gateway (e.g. mobile money / cards), automatic delivery using the same allocation + delivery-note services | Allocation engine, delivery-note template |

**SQLite → PostgreSQL migration path:** (1) schema is defined only through SQLAlchemy models + versioned migrations, avoiding SQLite-only SQL; (2) UUIDs are the cross-system identity; (3) money as integers and timestamps as UTC ISO-8601 map directly to PostgreSQL `bigint`/`timestamptz`; (4) a migration script will export each table in dependency order and import it into PostgreSQL, then compare row counts and checksums. Encrypted key blobs move unchanged; the DEK moves to a server-side key manager.

---

## 9. Testing strategy (applies to every phase)

| Level | What | Where it runs |
|-------|------|---------------|
| Unit | Money maths, remaining-activation calculation, ranking algorithm, reference numbers, crypto round-trip, password hashing | My environment + your Mac |
| Integration | Full sale transaction, oversell attempts, cancellation rules, concurrent allocation, migrations, backup → restore round trip, PDF generation (text extracted and checked) | My environment + your Mac |
| UI smoke | Each screen opens, forms validate, tables search (pytest-qt, offscreen) | My environment + your Mac |
| macOS-specific | Keychain, `.app` launch, Gatekeeper, printing, Retina rendering, M-series performance | **Your Mac only** (step-by-step checklist provided each phase) |

Target: ≥ 90 % test coverage on `services`, `security` and `core`.
