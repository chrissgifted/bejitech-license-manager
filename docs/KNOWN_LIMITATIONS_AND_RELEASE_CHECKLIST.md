# Known limitations and final release checklist

## Known limitations (release 1.0.0)

| Area | Limitation |
|---|---|
| macOS testing | Developed and tested on Linux. Keychain, `.app`/`.dmg` build, Gatekeeper, printing and Retina appearance have **not** been verified on a Mac yet |
| Signing | Builds are ad-hoc signed. Other Macs will show a Gatekeeper warning until you sign and notarize with a Developer ID (see SIGNING_AND_NOTARIZATION.md) |
| Sales | The New Sale screen sells one product per sale (one key or several keys for that product). The database already supports several products per sale |
| Email | "Prepare email" opens your email app with subject and message; the PDF must be attached by hand (email links cannot attach files) |
| Backups | Manual only. There is no automatic scheduled backup yet |
| Restore | The app closes after a restore and must be reopened |
| Users | One administrator account; no staff roles |
| Dashboard | Figures and lists only; no revenue chart |
| Product data | Seeded Office products have no download link (please add verified links). The Windows 11 link points to Microsoft's official download page but is marked "not verified" until you check it |
| Logos | PNG or JPG only (no SVG). Logos are not bundled; upload your approved logos |
| PDF fonts | Delivery notes use built-in Helvetica/Courier: Latin letters are fine, but characters outside Latin-1 (emoji, non-Latin scripts) will not display |
| Login throttling | The wait after 5 failed logins is held in memory and resets if the app is restarted (the failure count itself is saved) |
| Keychain prompts | An unsigned app is re-identified after each rebuild, so macOS may ask for Keychain access again |
| App size | About 250 MB because Qt is bundled |
| Migrations | Phase 1 planned Alembic; a small built-in migration runner was used instead (more reliable inside PyInstaller, one less dependency). It backs up the database before upgrading it |

## Final release checklist

Tick each item on your Mac.

**Build**
- [ ] `./packaging/build_macos.sh --dmg` completes: tests pass, `.app` built, packaged self-test says ALL PASSED
- [ ] `dist/BejitechLicenseManager-1.0.0.dmg` exists and opens; app drags into Applications

**First run**
- [ ] App opens (right-click → Open the first time)
- [ ] Administrator and recovery passphrase created; Keychain access allowed
- [ ] Settings: phone and email entered; appear on the next delivery note

**Workflow**
- [ ] Add a product with a logo and verified download link
- [ ] Add licence keys (single and bulk); duplicate key is refused
- [ ] Reveal and copy a key; clipboard clears after the set time
- [ ] New sale: recommendation shown, sale saved, delivery note opens
- [ ] Delivery note: logo, key, clickable link, instructions correct; Save PDF and Print work
- [ ] Prepare email opens Mail with the message; PDF shown in Finder
- [ ] Mark activation confirmed; cancel a different sale and check stock behaves as expected
- [ ] Reports export to PDF and CSV and open in Preview / Numbers
- [ ] Auto-lock after idle time; Lock button works

**Backup and recovery**
- [ ] Create backup to an external disk or iCloud Drive; history shows "Verified"
- [ ] Verify the backup file
- [ ] (On a test account or second Mac) restore the backup and sign in with the original account
- [ ] Recovery passphrase works: delete the Keychain item `com.bejitech.licensemanager` in Keychain Access, reopen the app, enter the passphrase, keys readable again

**Before relying on it**
- [ ] Real data entered and a backup made
- [ ] Recovery passphrase and backup password stored safely
- [ ] (Optional) Developer ID signing and notarization done
