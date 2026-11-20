"""Quick end-to-end check that also works inside the packaged app:

    "Bejitech License Manager.app/Contents/MacOS/Bejitech License Manager" --self-test

Uses a temporary folder and an in-memory key, so it never touches your real data or Keychain.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path


def run_self_test() -> int:
    from bejitech import __version__
    from bejitech.config.paths import AppPaths
    from bejitech.core.dto import CustomerInput, LicenseInput, SaleInput
    from bejitech.security.keystore import MemoryKeyStore
    from bejitech.services.context import AppContext

    tmp = Path(tempfile.mkdtemp(prefix="bejitech-selftest-"))
    steps = []
    ok = True

    def step(name, fn):
        nonlocal ok
        try:
            fn()
            steps.append(f"PASS  {name}")
        except Exception as exc:  # noqa: BLE001
            ok = False
            steps.append(f"FAIL  {name}: {exc}")

    try:
        ctx = AppContext.open(AppPaths(root=tmp / "data", logs=tmp / "logs"), MemoryKeyStore())
        step("database created and migrated", lambda: None)
        step("administrator + encryption key", lambda: ctx.auth.create_admin("Test", "test", "selftest-pass",
                                                                              "selftest recovery phrase"))
        pid = ctx.catalogue.list_products()[0].id
        step("add encrypted licence key", lambda: ctx.inventory.add_license(LicenseInput(
            product_id=pid, license_key="TEST1-TEST2-TEST3-TEST4-TEST5", purchase_date="2026-01-01",
            purchase_cost_minor=1000, permitted_capacity=2)))
        cid = ctx.customers.save(CustomerInput(full_name="Self Test"))
        holder = {}
        step("sale with allocation", lambda: holder.update(sid=ctx.sales.create_sale(
            SaleInput(cid, pid, 1, 5000, "CASH", "2026-01-02"))))
        step("delivery note PDF", lambda: ctx.delivery_notes.generate_for_sale(holder["sid"]).stat())
        step("encrypted backup + verify", lambda: ctx.backup.verify_backup(
            ctx.backup.create_backup(tmp / "bk", "selftest-pass"), "selftest-pass"))
        step("inventory consistency", lambda: (_ for _ in ()).throw(AssertionError("mismatch"))
             if ctx.inventory.verify_consistency() else None)

        def qt_modules():
            import PySide6.QtPdf  # noqa: F401
            import PySide6.QtPdfWidgets  # noqa: F401
            import PySide6.QtPrintSupport  # noqa: F401
        step("Qt PDF preview and printing modules", qt_modules)

        def keychain():
            import keyring
            keyring.get_keyring()
        step("keyring backend available", keychain)
        ctx.db.dispose()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"Bejitech License Manager {__version__} self-test")
    print("\n".join(steps))
    print("RESULT:", "ALL PASSED" if ok else "FAILURES FOUND")
    return 0 if ok else 1
