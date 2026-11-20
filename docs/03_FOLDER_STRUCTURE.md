# Bejitech License Manager: Project Folder and Module Structure

Phase 1 deliverable. This is the structure Phase 2 will create. Files marked *(Pn)* are first written in that phase.

```
bejitech-license-manager/
├── README.md                         How to install, run, test
├── DEVELOPMENT_PROGRESS.md           Phase tracker (updated every phase)
├── pyproject.toml                    Project metadata, tool config (pytest, coverage)   (P2)
├── requirements.txt                  Pinned runtime dependencies                         (P2)
├── requirements-dev.txt              pytest, pytest-qt, pytest-cov, pyinstaller          (P2)
├── run.py                            Dev entry point: python run.py                       (P2)
│
├── docs/
│   ├── 01_ARCHITECTURE.md
│   ├── 02_DATABASE_SCHEMA.md
│   ├── 03_FOLDER_STRUCTURE.md
│   ├── 04_SCREEN_WIREFRAMES.md
│   ├── 05_DEVELOPMENT_ENVIRONMENT.md
│   ├── 06_DEVELOPMENT_CHECKLIST.md
│   ├── USER_MANUAL.md                                                                     (P7)
│   ├── INSTALLATION_GUIDE.md                                                              (P7)
│   └── SIGNING_AND_NOTARIZATION.md                                                        (P7)
│
├── db/
│   ├── schema_v1.sql                 Reference schema (this phase)
│   └── check_schema.py               Schema constraint check (this phase)
│
├── src/bejitech/
│   ├── __init__.py                   __version__
│   ├── __main__.py                   python -m bejitech
│   ├── selftest.py                   --self-test end-to-end check (works in the packaged app)
│   ├── app.py                        Builds QApplication, wires services, shows login → main window
│   │
│   ├── config/
│   │   ├── paths.py                  App-support, logs, logos, notes, backups dirs (platformdirs)
│   │   └── app_config.py             Constants, defaults, feature flags
│   │
│   ├── core/                         No internal imports: pure domain
│   │   ├── enums.py                  LicenseStatus, StockState, AllocationStatus, PaymentMethod…
│   │   ├── dto.py                    Dataclasses passed between UI and services
│   │   ├── money.py                  Money type (int minor units + currency), formatting "TZS 150,000"
│   │   ├── references.py             INV/SAL/DN/CUS number formats
│   │   └── errors.py                 OversellError, ExpiredLicenseError, AuthError, ValidationError…
│   │
│   ├── db/
│   │   ├── engine.py                 Engine, session factory, PRAGMAs (foreign_keys, WAL)
│   │   ├── models.py                 SQLAlchemy ORM models (mirror schema_v1.sql)
│   │   ├── repositories/             One module per aggregate (products, licenses, sales…)
│   │   ├── seed.py                   Initial catalogue + licence types
│   │   ├── migrations.py             Versioned migration runner (pre-upgrade backup)
│   │   └── sql/0001_initial.sql      Initial schema
│   │
│   ├── security/
│   │   ├── crypto.py                 AES-256-GCM encrypt/decrypt, HMAC fingerprint
│   │   ├── keystore.py               DEK in macOS Keychain via keyring; escrow wrap/unwrap
│   │   ├── passwords.py              Argon2id hash/verify, KDF
│   │   └── masking.py                XXXXX-…-7HQ2D masking, log redaction
│   │
│   ├── services/                     Business logic. No Qt imports.
│   │   ├── catalogue_service.py      (P2)
│   │   ├── inventory_service.py      (P3)
│   │   ├── allocation_service.py     (P3/P4) recommendation + allocate/release/confirm
│   │   ├── customer_service.py       (P4)
│   │   ├── sales_service.py          (P4) create/cancel sale (atomic)
│   │   ├── delivery_note_service.py  (P5)
│   │   ├── reporting_service.py      (P6)
│   │   ├── auth_service.py           (P6, minimal first-run setup earlier if needed)
│   │   ├── audit_service.py          (P3 onward)
│   │   ├── backup_service.py         (P6)
│   │   └── settings_service.py       (P2)
│   │
│   ├── pdf/
│   │   ├── styles.py                 Colours, fonts, spacing
│   │   ├── delivery_note.py          A4 delivery note builder                            (P5)
│   │   └── report_pdf.py             Report exports                                      (P6)
│   │
│   ├── exports/
│   │   └── csv_export.py                                                                 (P6)
│   │
│   ├── ui/
│   │   ├── main_window.py            Window, sidebar, stacked pages, status bar
│   │   ├── sidebar.py
│   │   ├── theme/                    style.qss (light), style_dark.qss, colours.py
│   │   ├── widgets/                  SearchableTable, MaskedKeyField, MoneyEdit, StatCard,
│   │   │                             LogoPicker, ConfirmDialog, EmptyState
│   │   ├── views/                    dashboard.py, products.py, inventory.py, new_sale.py,
│   │   │                             customers.py, sales_history.py, delivery_notes.py,
│   │   │                             reports.py, backup_restore.py, settings.py, login.py
│   │   └── dialogs/                  product_form.py, license_form.py, customer_form.py,
│   │                                 cancel_sale.py, reveal_key.py, first_run_setup.py
│   │
│   └── resources/
│       ├── icons/                    App icon (.icns), sidebar icons (SVG)
│       ├── fonts/                    Open-licence fonts for PDF (e.g. Inter / Noto Sans)
│       └── placeholder_logos/        Neutral product placeholders (no trademarks)
│
├── tests/
│   ├── conftest.py                   Temp DB, fake keystore (no real Keychain in tests)
│   ├── unit/                         money, references, crypto, masking, ranking
│   ├── integration/                  sales transactions, oversell, cancellation, migrations,
│   │                                 backup/restore, PDF content
│   └── ui/                           pytest-qt smoke tests (offscreen)
│
├── packaging/                                                                            (P7)
│   ├── bejitech.spec                 PyInstaller spec (arm64, Info.plist, icon)
│   ├── build_macos.sh                Build .app, ad-hoc sign, optional .dmg via hdiutil
│   └── entitlements.plist
│
└── scripts/
    ├── dev_reset_db.py               Wipe local dev data (asks for confirmation)
    └── dev_sample_data.py            Fake customers/keys for trying the app
```

## Dependency direction (enforced by a test)

```
ui  →  services  →  db / security / pdf / exports  →  core
config is usable by all; core imports nothing internal
```

A test in `tests/unit/test_architecture.py` will fail if any module under `services/`, `db/`, `security/` or `core/` imports `PySide6`. This guarantees the business logic stays reusable for the future web/mobile backend.

## Runtime data (not in the project folder)

```
~/Library/Application Support/Bejitech License Manager/
├── bejitech.db
├── logos/
├── delivery_notes/2026/
└── backups/
~/Library/Logs/Bejitech License Manager/app.log
```
