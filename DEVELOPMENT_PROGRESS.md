# DEVELOPMENT_PROGRESS.md: Bejitech License Manager

## Web version: Phase 1 done (20 Nov 2026)
Plan approved: web app at app.bejitech.com on Render (Frankfurt), about $14/month.

- **Same database rules on PostgreSQL.** New `db/sql/0001_initial.pg.sql` (same tables, CHECK constraints,
  append-only triggers, views). Each unit of work takes `pg_advisory_xact_lock`, the PostgreSQL equivalent of
  `BEGIN IMMEDIATE`, so overselling and partial sales stay impossible. The desktop app keeps using SQLite.
- **Migration 2** (both databases): two-step login secret (encrypted with the licence-key key), replay guard,
  lockout stored in the database (survives restarts).
- **Server key store**: `BEJITECH_DEK` environment variable instead of the macOS Keychain.
- **Web server** (`src/bejitech/web`, FastAPI): first-run setup protected by a setup code, password + 6-digit
  authenticator code, signed HTTPS-only cookie, sign-out after inactivity (Settings auto-lock minutes), CSRF
  tokens on every form, rate limits, strict security headers. Pages: Dashboard and Products (phone and desktop).
  `python -m bejitech.web serve | genkey | reset-two-step USER`.
- **Hosting files**: `render.yaml` (web service + PostgreSQL + 1 GB disk), `requirements-web.txt`,
  [docs/WEB_SETUP_GUIDE.md](docs/WEB_SETUP_GUIDE.md) (step by step for Render and Namecheap).
- **Tests**: SQLite 92 passed (82 existing + 10 web); PostgreSQL 79 passed, 6 skipped (they read the SQLite file
  directly). Run on PostgreSQL with `BEJITECH_TEST_DATABASE_URL=postgresql://… pytest tests/unit tests/integration tests/web`.
- Screenshots: `docs/screenshots/web/`.

Next: Phase 2 (remaining screens), Phase 3 (go online, import Mac data), Phase 4 (test and switch).

## Current phase (desktop app)
**Phase 7: Testing, Packaging and Final Delivery.** All code and documents are written. Automated testing is
complete in the development environment (Linux). **The macOS build and on-Mac testing are waiting for you**
(see "Requires user-side testing" below).

## Approval status

| Phase | Status | Approval |
|-------|--------|----------|
| 1 Planning & architecture | Done | Approved 18 Nov 2026 ("continue to last phase, I will test at the end") |
| 2 Interface & product catalogue | Done, tested on Linux | Covered by the same instruction |
| 3 Licence inventory | Done, tested on Linux | 〃 |
| 4 Customers & sales | Done, tested on Linux | 〃 |
| 5 PDF delivery notes | Done, tested on Linux | 〃 |
| 6 Reports, security, backup | Done, tested on Linux | 〃 |
| 7 Testing, packaging, delivery | Code, scripts and docs done; **Mac build and Mac testing pending (you)** | Awaiting your test results |

## Completed tasks by phase

**Phase 2: Interface and catalogue.** Main window with sidebar for all 10 sections; theme; dashboard; product
catalogue with add/edit/search/filter/archive, logo upload (PNG/JPG, resized, stored in Application Support),
download URL + friendly label + "verified" flag, instructions, low-stock level; four products preconfigured;
Settings for seller name, business name, phone, email, address. Data stored in
`~/Library/Application Support/Bejitech License Manager/`. Versioned migrations with pre-upgrade backup.

**Phase 3: Inventory.** AES-256-GCM encrypted keys (key in macOS Keychain via `keyring`), masked display, reveal for
30 s and copy with automatic clipboard clearing, password re-check after 5 minutes, audit of every reveal/copy;
duplicate-key detection (HMAC fingerprint); single and bulk entry; TZS or USD cost with exchange rate; capacity,
allocated, confirmed, remaining; five stock states; expiry; restrictions; disable/enable; capacity adjustment;
append-only allocation history; low-stock alerts. Database CHECK constraint makes overselling impossible.

**Phase 4: Customers and sales.** Customer register, search, archive, purchase history; New Sale screen with smart
recommendation (expiring soonest → partly used → oldest) and automatic split across keys; multi-customer rule;
price, discount, total; payment method and reference; one atomic transaction (`BEGIN IMMEDIATE`) for sale +
allocation + inventory + history + delivery-note number; confirm activation; safe cancellation (release only when
not confirmed and allowed, otherwise consumed); sales history with filters and CSV export.

**Phase 5: Delivery notes.** Premium A4 PDF: accent colour taken from the product logo, logo or neutral badge, seller
and customer blocks, DN number, date, sale ref, product/edition/platform/licence type, key(s) with activation count,
clickable friendly download link (raw URL not printed), installation and activation instructions, optional
signature, footer, VOID watermark. Preview inside the app, save, print, prepare email (honest: no automatic
attachment), show in Finder, re-issue as a new revision. PDF hash stored; a changed/missing PDF is regenerated.

**Phase 6: Reports, security, backup.** Dashboard figures with period filter; inventory, sales, customer,
activation and profit reports (profit includes cost of consumed activations from cancelled sales) with PDF and
CSV export; first-run administrator setup; Argon2id passwords; login lockout after 5 failures; auto-lock after
inactivity; recovery passphrase that restores the Keychain key; change password / passphrase; audit-log viewer
(append-only table); encrypted backups (Argon2id + AES-256-GCM, includes DB, logos, PDFs and the wrapped key),
automatic verification (hashes + SQLite integrity check), restore with safety backup; inventory consistency check.

**Phase 7: Testing and packaging.** 76 automated tests; `--self-test` command; PyInstaller spec, entitlements,
`packaging/build_macos.sh` (tests → icon → `.app` → ad-hoc sign → packaged self-test → optional `.dmg`);
installation guide, user manual, signing/notarization guide, test results, known limitations, release checklist;
demo-data script; screenshots.

## Tests performed

| Test | Where | Result |
|---|---|---|
| 82 automated tests (unit, integration, UI smoke via pytest-qt offscreen) | Linux, Python 3.13.18, PySide6 6.12.0 | **82 passed, 0 failed** (re-run 20 Nov 2026 for 1.0.1) |
| Coverage of non-UI code | same | 92 % |
| `run.py --self-test` | same | All 9 steps passed |
| PyInstaller build from `packaging/bejitech.spec` + `--self-test` of the frozen build | **Linux** (not macOS) | Built; all 9 steps passed |
| Real app entry point launched, signed in, quit cleanly | Linux offscreen | Exit code 0 (fixed a crash-on-quit found here) |
| Screens and delivery note inspected visually | Linux offscreen render | OK; see `docs/screenshots/` |

Full list: [docs/TEST_RESULTS.md](docs/TEST_RESULTS.md).

## Requires user-side testing (on your Mac)
1. `./packaging/build_macos.sh --dmg` (builds the `.app` and `.dmg`; nothing has been built for macOS yet).
2. First launch, Gatekeeper "Open", Keychain "Always Allow".
3. Printing, Preview, Mail and Finder integration.
4. Appearance on your screen.
5. The full [release checklist](docs/KNOWN_LIMITATIONS_AND_RELEASE_CHECKLIST.md).

## Version 1.0.1 (20 Nov 2026): fix from your testing
- **Licence type can now be corrected when editing a key.** The Edit licence dialog has a *Licence type* field
  and the *Product* can be changed too. Choosing another type files the key under the same product with that
  type (created automatically with the same prices, link and instructions if it doesn't exist yet). Both fields
  are locked once any activation of the key has been sold, so past sales and delivery notes can't change; the
  dialog explains how to unlock it (cancel with activations returned to stock) or to disable and re-add the key.
  The same Licence type field is available when adding keys. Every change is written to the audit log.
- 6 new tests (service rules + dialog). Full suite: **82 passed, 0 failed** (Linux).

## Defects found and fixed during development
- New product could fail to save (premature database flush) → fixed, test added.
- Failed-login counter was rolled back so the lockout never triggered → fixed, test added.
- App could crash when quitting (Qt PDF viewer destroyed late) → fixed by explicit cleanup, verified.

## Known issues / limitations
See [docs/KNOWN_LIMITATIONS_AND_RELEASE_CHECKLIST.md](docs/KNOWN_LIMITATIONS_AND_RELEASE_CHECKLIST.md). Main ones:
not yet tested on macOS; ad-hoc signing only; one product per sale in the UI; manual backups only; email attachment
by hand; Office download links need to be added by you.

## Decisions taken without asking (easy to change)
- Code delivered in the project files folder; no GitHub repository created.
- "Bejitech" shown under your name on delivery notes (Settings → Business name; leave empty to hide).
- Built-in migration runner instead of Alembic.
- Key display shows the last 5 characters.

## Files
Source in `src/bejitech/` (config, core, db, security, services, pdf, exports, ui), tests in `tests/`, packaging in
`packaging/`, scripts in `scripts/`, documents in `docs/`. Phase 1 design documents updated where the
implementation differs.

## Next steps
1. You: build and test on your Mac using the release checklist, and send back anything that fails
   (the output of `--self-test` and `~/Library/Logs/Bejitech License Manager/app.log` help).
2. Me: fix what you find.
3. Later phases (8 Windows, 9 iPhone, 10 online store) only when you ask.
