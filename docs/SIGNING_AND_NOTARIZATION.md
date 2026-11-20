# macOS signing and notarization

The build script signs the app **ad-hoc**. That is enough to run it on your own Mac after right-click → Open.
To give the app to other people without Gatekeeper warnings you need Apple's Developer ID signing and notarization.

## Requirements
- Apple Developer Program membership (US$99/year), enrolled as an individual or organisation.
- A **Developer ID Application** certificate installed in your login Keychain (Xcode → Settings → Accounts → Manage Certificates).
- An app-specific password for your Apple ID (appleid.apple.com → Sign-In and Security).

## Steps
```bash
# 1. Build with your identity (hardened runtime + entitlements are applied by PyInstaller)
export BEJITECH_CODESIGN_IDENTITY="Developer ID Application: Your Name (TEAMID)"
./packaging/build_macos.sh --dmg

# 2. Re-sign deeply with hardened runtime (covers bundled Qt frameworks)
codesign --force --deep --options runtime --timestamp \
  --entitlements packaging/entitlements.plist \
  --sign "$BEJITECH_CODESIGN_IDENTITY" "dist/Bejitech License Manager.app"

# 3. Store notarization credentials once
xcrun notarytool store-credentials bejitech --apple-id you@example.com --team-id TEAMID

# 4. Notarize the DMG and staple the ticket
xcrun notarytool submit dist/BejitechLicenseManager-1.0.1.dmg --keychain-profile bejitech --wait
xcrun stapler staple dist/BejitechLicenseManager-1.0.1.dmg

# 5. Check
spctl --assess --type open --context context:primary-signature -v dist/BejitechLicenseManager-1.0.1.dmg
```

## Notes
- A signed app keeps the same identity across updates, so the Keychain stops asking for permission after each rebuild.
- If notarization fails, run `xcrun notarytool log <submission-id> --keychain-profile bejitech` to see which file was rejected.
- None of these steps have been run yet; they need your Apple Developer account.
