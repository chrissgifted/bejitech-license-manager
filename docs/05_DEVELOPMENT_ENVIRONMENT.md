# Bejitech License Manager: Development Environment Requirements

Phase 1 deliverable.

## 1. Your MacBook (where the app runs and is tested)

| Requirement | Detail |
|-------------|--------|
| Mac | Apple Silicon (M1, M2, M3, M4 or later). Intel Macs are not a target, though the code would likely run |
| macOS | macOS 13 Ventura or later recommended. Recent Qt 6 releases drop older macOS versions; the exact minimum for the pinned PySide6 version is confirmed in Phase 2. Please tell me your macOS version |
| Disk | ~2 GB free for Python, dependencies and builds |
| Python | **3.13** (3.12 also fine), from python.org "macOS 64-bit universal2 installer" or Homebrew (`brew install python@3.13`). Do **not** use the system `/usr/bin/python3` |
| Xcode Command Line Tools | `xcode-select --install` (needed for packaging and `codesign`) |
| Git | Comes with the Command Line Tools |
| Editor (optional) | VS Code with the Python extension, or PyCharm Community |
| Apple Developer account | **Not required** until you want a signed, notarized app for other Macs (US$99/year). Unsigned builds run on your own Mac after right-click → Open |

## 2. Python dependencies (planned, pinned in Phase 2)

Latest versions on PyPI as of 18 Nov 2026 (checked during Phase 1):

| Package | Version | Purpose |
|---------|---------|---------|
| PySide6 | 6.12.0 | Desktop UI (includes QtCharts and QtPdf for preview) |
| SQLAlchemy | 2.1.9 | Database access |
| reportlab | 5.1.0 | PDF generation (installs Pillow) |
| cryptography | 50.0.2 | AES-256-GCM, HMAC |
| argon2-cffi | 25.1.0 | Argon2id password hashing / KDF |
| keyring | 25.7.0 | macOS Keychain access |
| platformdirs | 4.14.7 | Correct data folders per OS |
| **Dev only** | | |
| pytest | 9.2.0 | Tests |
| pytest-qt | 4.5.0 | UI tests |
| pytest-cov | latest | Coverage |
| pyinstaller | 6.22.3 | Build `.app` |

That is 7 runtime packages (Alembic was dropped in Phase 2 in favour of a built-in migration runner), all mainstream and actively maintained. No web or cloud libraries.

## 3. One-time setup on your Mac (used from Phase 2)

```bash
# 1. Tools
xcode-select --install
python3.13 --version        # should print Python 3.13.x

# 2. Get the project (folder location to be agreed, see open questions)
cd ~/Projects/bejitech-license-manager

# 3. Virtual environment
python3.13 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt

# 4. Run the app
python run.py

# 5. Run the tests
pytest
```

Each phase's `DEVELOPMENT_PROGRESS.md` entry will repeat the exact commands for that phase, plus a short manual test script ("click Products, add a product called X, expect Y").

## 4. My build environment (how I will develop and test)

| Item | Detail |
|------|--------|
| Where | A Linux cloud container (Python 3.13, SQLite 3.53) |
| What I can verify | All business logic, database, migrations, encryption, PDF generation and content, backup/restore, and UI smoke tests with Qt's offscreen platform |
| What I **cannot** verify | macOS Keychain, the look of the app on a Retina screen, macOS print dialog, building/launching the `.app`/`.dmg`, Gatekeeper, real M-series performance |
| How we close that gap | Each phase lists "requires user-side testing" items with exact steps. Optionally, a GitHub Actions macOS (Apple Silicon) runner could run tests and build the `.app` automatically if you want a repository |
| Keychain in tests | Tests use a fake in-memory keystore; the real Keychain path is a small module tested on your Mac |

## 5. Source control and delivery (needs your decision)

Options:
1. **GitHub repository (recommended):** private repo under your account; I push each phase on a branch and open a pull request you approve. Gives history, easy download (`git clone`/`git pull`), and optional macOS CI.
2. **Project files only:** I keep writing files here and you download the folder each phase.
3. **Directly into a folder on your Mac:** this thread is linked to your computer, so I can write the project into a folder you choose (e.g. `~/Projects/bejitech-license-manager`).

I will not create or push to any repository until you choose.

## 6. Coding standards

- Type hints everywhere; `ruff` style rules (formatting via `ruff format`, optional dev tool).
- Docstrings on public service methods.
- No Qt imports outside `bejitech.ui` (checked by a test).
- Every business rule (R1–R9 in the architecture doc) has at least one automated test.
- Commit messages describe the user-visible change.
