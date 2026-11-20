# Bejitech License Manager

Offline macOS desktop application (Python · PySide6 · SQLite) for managing a digital software licence business:
product catalogue, encrypted licence-key inventory with activation balances, customers, sales with smart key
allocation, product-branded PDF delivery notes, reports, audit log and encrypted backups.

**Status:** Phases 1–7 implemented. 82 automated tests pass in the development environment (Linux).
**Not yet tested on a Mac:** see [DEVELOPMENT_PROGRESS.md](DEVELOPMENT_PROGRESS.md) for exactly what you need to check.

## Quick start on your Mac (from source)

```bash
xcode-select --install                     # once
cd ~/Projects/bejitech-license-manager     # wherever you put this folder
python3 -m venv .venv                       # needs Python 3.12 or 3.13
source .venv/bin/activate
pip install -r requirements-dev.txt
python run.py                               # opens the app
```

Run the tests: `QT_QPA_PLATFORM=offscreen python -m pytest`
Quick self-check: `python run.py --self-test`

Try it with demo data first (kept in a separate folder, never your real data):

```bash
BEJITECH_DATA_DIR=~/BejitechDemo python scripts/dev_sample_data.py
BEJITECH_DATA_DIR=~/BejitechDemo python run.py      # sign in: admin / demo-password
```

## Build the Mac app

```bash
./packaging/build_macos.sh          # → dist/Bejitech License Manager.app
./packaging/build_macos.sh --dmg    # also → dist/BejitechLicenseManager-1.0.1.dmg
```

## Web version (in progress)
Same services, served as a website (FastAPI + PostgreSQL). Try it locally:

```bash
pip install -r requirements-dev.txt
export BEJITECH_SECRET_KEY=$(python -c "import secrets;print(secrets.token_urlsafe(48))")
export BEJITECH_DEK=$BEJITECH_SECRET_KEY BEJITECH_SETUP_TOKEN=try-it BEJITECH_COOKIE_SECURE=0 BEJITECH_DATA_DIR=~/BejitechWebTrial
PYTHONPATH=src python -m bejitech.web serve      # http://127.0.0.1:8000
```

Going online: [docs/WEB_SETUP_GUIDE.md](docs/WEB_SETUP_GUIDE.md).

## Documents
- [Installation guide](docs/INSTALLATION_GUIDE.md) · [User manual](docs/USER_MANUAL.md)
- [Signing and notarization](docs/SIGNING_AND_NOTARIZATION.md) · [Test results](docs/TEST_RESULTS.md)
- [Known limitations and release checklist](docs/KNOWN_LIMITATIONS_AND_RELEASE_CHECKLIST.md)
- Phase 1 design: [Architecture](docs/01_ARCHITECTURE.md) · [Database](docs/02_DATABASE_SCHEMA.md) ·
  [Folders](docs/03_FOLDER_STRUCTURE.md) · [Wireframes](docs/04_SCREEN_WIREFRAMES.md) ·
  [Environment](docs/05_DEVELOPMENT_ENVIRONMENT.md) · [Checklist](docs/06_DEVELOPMENT_CHECKLIST.md)

## Where your data lives
`~/Library/Application Support/Bejitech License Manager/` (database, logos, delivery notes, backups).
The encryption key for licence keys is in the macOS Keychain (item `com.bejitech.licensemanager`).
