# PyInstaller spec for Bejitech License Manager.
# Build on the Mac with:  ./packaging/build_macos.sh
import os
import sys

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)
from bejitech import __version__  # noqa: E402

APP_NAME = "Bejitech License Manager"
IS_MAC = sys.platform == "darwin"

a = Analysis(
    [os.path.join(ROOT, "run.py")],
    pathex=[SRC],
    datas=[
        (os.path.join(SRC, "bejitech", "db", "sql", "0001_initial.sql"), "bejitech/db/sql"),
        (os.path.join(SRC, "bejitech", "resources", "app_icon.png"), "bejitech/resources"),
    ],
    hiddenimports=[
        "bejitech.resources",
        "keyring.backends.macOS",
        "keyring.backends.Windows",
        "keyring.backends.SecretService",
        "argon2._ffi",
        "PySide6.QtPdf",
        "PySide6.QtPdfWidgets",
        "PySide6.QtPrintSupport",
    ],
    excludes=[
        "tkinter",
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
        "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.QtQuick3D", "PySide6.QtMultimedia",
        "PySide6.QtBluetooth", "PySide6.QtSensors", "PySide6.QtCharts", "PySide6.QtDataVisualization",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    console=False,
    target_arch="arm64" if IS_MAC else None,
    codesign_identity=os.environ.get("BEJITECH_CODESIGN_IDENTITY") or None,
    entitlements_file=os.path.join(SPECPATH, "entitlements.plist") if IS_MAC else None,
)
coll = COLLECT(exe, a.binaries, a.datas, name=APP_NAME)

if IS_MAC:
    icon = os.path.join(ROOT, "build", "AppIcon.icns")
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=icon if os.path.exists(icon) else None,
        bundle_identifier="com.bejitech.licensemanager",
        version=__version__,
        info_plist={
            "CFBundleName": APP_NAME,
            "CFBundleDisplayName": APP_NAME,
            "CFBundleShortVersionString": __version__,
            "CFBundleVersion": __version__,
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "13.0",
            "NSHumanReadableCopyright": "© Bejitech",
            "LSApplicationCategoryType": "public.app-category.business",
        },
    )
