#!/usr/bin/env bash
# Build "Bejitech License Manager.app" (and optionally a .dmg) on an Apple Silicon Mac.
#   ./packaging/build_macos.sh          → dist/Bejitech License Manager.app
#   ./packaging/build_macos.sh --dmg    → also dist/BejitechLicenseManager-<version>.dmg
set -euo pipefail
cd "$(dirname "$0")/.."

APP="Bejitech License Manager"
[[ "$(uname -s)" == "Darwin" ]] || { echo "This script must run on macOS."; exit 1; }
[[ "$(uname -m)" == "arm64" ]] || echo "Warning: not an Apple Silicon Mac; the build targets arm64."

if [[ ! -d .venv ]]; then python3 -m venv .venv; fi
source .venv/bin/activate
pip install --upgrade pip >/dev/null
pip install -r requirements-dev.txt

echo "==> Running tests"
QT_QPA_PLATFORM=offscreen python -m pytest -q

echo "==> Making app icon"
rm -rf build/AppIcon.iconset && mkdir -p build/AppIcon.iconset
SRC_ICON=src/bejitech/resources/app_icon.png
for s in 16 32 128 256 512; do
  sips -z $s $s "$SRC_ICON" --out "build/AppIcon.iconset/icon_${s}x${s}.png" >/dev/null
  sips -z $((s*2)) $((s*2)) "$SRC_ICON" --out "build/AppIcon.iconset/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns build/AppIcon.iconset -o build/AppIcon.icns

echo "==> Building .app"
rm -rf "dist/$APP" "dist/$APP.app"
pyinstaller --noconfirm --clean packaging/bejitech.spec

if [[ -z "${BEJITECH_CODESIGN_IDENTITY:-}" ]]; then
  echo "==> Ad-hoc signing (no Developer ID set; app runs on this Mac only)"
  codesign --force --deep --sign - "dist/$APP.app"
fi

echo "==> Self-test of the packaged app"
"dist/$APP.app/Contents/MacOS/$APP" --self-test

if [[ "${1:-}" == "--dmg" ]]; then
  VERSION=$(python -c "import sys; sys.path.insert(0,'src'); import bejitech; print(bejitech.__version__)")
  STAGE=build/dmg && rm -rf "$STAGE" && mkdir -p "$STAGE"
  cp -R "dist/$APP.app" "$STAGE/"
  ln -s /Applications "$STAGE/Applications"
  hdiutil create -volname "$APP" -srcfolder "$STAGE" -ov -format UDZO "dist/BejitechLicenseManager-$VERSION.dmg"
  echo "==> DMG: dist/BejitechLicenseManager-$VERSION.dmg"
fi
echo "==> Done: dist/$APP.app"
