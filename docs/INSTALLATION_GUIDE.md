# Installation guide

## Option A: build the app yourself (recommended for now)

1. Install Apple's command-line tools: open Terminal and run `xcode-select --install`.
2. Install Python 3.13 from python.org ("macOS 64-bit universal2 installer").
3. Copy the `bejitech-license-manager` folder to your Mac, e.g. `~/Projects/`.
4. In Terminal:
   ```bash
   cd ~/Projects/bejitech-license-manager
   ./packaging/build_macos.sh --dmg
   ```
   The script creates a virtual environment, installs dependencies, runs all tests, builds the app,
   signs it for your Mac (ad-hoc), runs the packaged app's self-test and makes a `.dmg`.
5. Open `dist/BejitechLicenseManager-1.0.1.dmg` and drag the app to **Applications**.

## First launch

Because the app is not signed with an Apple Developer ID, macOS may say it "cannot be opened".
Right-click (or Control-click) the app in Applications → **Open** → **Open**. You only need to do this once.
On newer macOS versions you may instead need **System Settings → Privacy & Security → Open Anyway**.

On first launch:
1. Create the administrator account (password 8+ characters).
2. Set a **recovery passphrase** (12+ characters). Write it down and store it safely.
3. macOS may ask whether the app may use the Keychain. Choose **Always Allow**.

## Option B: run from source (for testing changes)
See the Quick start in `README.md`.

## Troubleshooting

| Problem | Fix |
|---|---|
| "App is damaged / can't be opened" | Right-click → Open, or run `xattr -dr com.apple.quarantine "/Applications/Bejitech License Manager.app"` |
| Keychain prompt every launch | Choose "Always Allow". Rebuilding an unsigned app changes its identity, so macOS asks again after each rebuild |
| "Encryption key was not found in the Keychain" | Enter your recovery passphrase when asked. The key is restored to the Keychain |
| App won't start | Run `"/Applications/Bejitech License Manager.app/Contents/MacOS/Bejitech License Manager" --self-test` in Terminal and check `~/Library/Logs/Bejitech License Manager/app.log` |
| `pip install` fails | Make sure you use Python 3.12 or 3.13 (`python3 --version`), not the system Python |
| Moving to a new Mac | Create a backup (Backup & Restore), install the app on the new Mac, create a temporary account, then restore the backup. Sign in with your original account afterwards |
