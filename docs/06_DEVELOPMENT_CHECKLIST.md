# Bejitech License Manager: Development Checklist

Phase 1 deliverable. Ticked only when implemented **and** verified. "🍎" = requires testing on your Mac.

## Phase 1: Planning and System Architecture
- [x] Requirements analysed (business rules R1–R9 in architecture doc)
- [x] Architecture designed (layered, Qt-free services)
- [x] SQLite schema designed (20 tables, 2 views)
- [x] Schema loaded and constraints checked in SQLite 3.53 (`db/check_schema.py`)
- [x] Folder and module structure defined
- [x] Screen wireframes for all 10 sections + login + PDF layout
- [x] Dependencies identified, versions checked on PyPI
- [x] Technical risks listed with mitigations
- [x] Development environment documented
- [x] **Your approval of Phase 1** (18 Nov 2026: continue through Phase 7, test at the end)

### Phase 1 acceptance checklist (for you to review)
- [ ] My understanding of the business (architecture §1) is correct
- [ ] Business rules R1–R9 match how you actually sell (especially multi-customer keys and cancellations)
- [ ] Product hierarchy Publisher → Product line → Version/Edition/Licence type works for you
- [ ] Database fields cover everything you record today
- [ ] Reference formats INV-/SAL-/DN-/CUS- are acceptable
- [ ] Screen layouts and navigation look right
- [ ] Delivery note layout contains everything customers need
- [ ] Security approach (password + recovery passphrase + Keychain) is acceptable
- [ ] Source-control option chosen (GitHub / project files / folder on your Mac)

## Phase 2: Interface and Product Catalogue
- [x] Project skeleton, `requirements.txt`, `pyproject.toml`, `run.py`
- [x] Paths module (Application Support), logging
- [x] SQLAlchemy models + migration `0001_initial` + seed data (built-in runner instead of Alembic)
- [x] Main window, sidebar, page switching, theme
- [x] Dashboard with real figures
- [x] Product list: search, filter, archive toggle
- [x] Add/Edit product dialog with validation and logo upload
- [x] Four preconfigured products seeded
- [x] Settings: seller name/phone/email
- [x] Tests: catalogue service, migrations, UI smoke
- [ ] 🍎 Launch on your Mac and run the manual test script

## Phase 3: License Inventory and Activation Tracking
- [x] Encryption module (AES-GCM) + Keychain keystore + recovery escrow
- [x] Add licence (single + bulk), duplicate detection
- [x] Masked display, reveal/copy with audit, clipboard clear
- [x] Capacity / allocated / remaining, five stock states
- [x] Oversell prevention (service + DB)
- [x] Allocation history view
- [x] Low-stock alerts
- [x] Disable / capacity adjustment with history
- [x] Tests: calculations, restrictions, expiry, crypto, oversell
- [ ] 🍎 Keychain behaviour on your Mac

## Phase 4: Customer and Sales Management
- [x] Customer CRUD, search, history
- [x] New Sale screen with recommendation engine
- [x] Price, discount, total calculation
- [x] Atomic sale transaction
- [x] Multi-key split allocation (automatic when no single key is enough)
- [x] Confirm activation action
- [x] Safe cancellation (release vs consumed)
- [x] Sales history with filters
- [x] Tests: inventory consistency, concurrent/double submit, cancellation rules

## Phase 5: PDF Delivery Notes
- [x] A4 template, product-adaptive accent and logo
- [x] Seller/customer blocks, DN number, date
- [x] Licence key, activations, clickable friendly download link
- [x] Installation/activation instructions, optional signature
- [x] Preview (QtPdf), export, print
- [x] Prepare email (subject/body + reveal PDF in Finder; honest about attachments)
- [x] Linked to sale; void on cancellation; regenerate as revision
- [x] Tests: PDF content and link annotation extracted and checked
- [ ] 🍎 Print and open in Preview on your Mac

## Phase 6: Reports, Security and Backup
- [x] Dashboard calculations complete
- [x] Inventory, sales, customer, activation, profit reports; PDF + CSV export
- [x] Administrator login, auto-lock, failed-login back-off
- [x] Audit log viewer
- [x] Encrypted backup, verification, restore with safety backup
- [x] "Verify inventory" consistency tool
- [x] Tests: backup → restore round trip, tampered backup rejected, profit maths

## Phase 7: Testing, Packaging and Delivery
- [x] Full automated test run with results file
- [x] End-to-end workflow tests
- [x] Defect fixes
- [ ] PyInstaller `.app` (arm64), optional `.dmg` (script and spec ready; spec verified by a Linux build; Mac build not yet run)
- [ ] 🍎 Build, launch and test on your Mac (M-series)
- [x] Installation guide, user manual, troubleshooting
- [x] Signing and notarization guide
- [x] Known limitations, final release checklist
