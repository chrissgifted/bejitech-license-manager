import pytest
from pypdf import PdfReader

from bejitech.core.dto import SaleInput
from bejitech.core.errors import AuthError, BackupError, KeyStoreError, ValidationError
from bejitech.exports.csv_export import write_csv
from bejitech.pdf.report_pdf import write_report_pdf
from bejitech.security.keystore import MemoryKeyStore
from bejitech.services.context import AppContext
from tests_support import PASSWORD, RECOVERY


def _business(ctx, helpers):
    helpers.add_key(ctx, key="PROFT-00001", capacity=5, cost=100000, allows_multiple_customers=True)  # 20,000 each
    c1, c2 = helpers.add_customer(ctx, "One"), helpers.add_customer(ctx, "Two")
    pid = helpers.product_id(ctx)
    s1 = ctx.sales.create_sale(SaleInput(c1, pid, 2, 85000, "CASH", "2026-11-10", discount_minor=10000))
    s2 = ctx.sales.create_sale(SaleInput(c2, pid, 1, 85000, "CARD", "2026-11-12"))
    return s1, s2


def test_dashboard_and_profit(ctx, helpers):
    s1, s2 = _business(ctx, helpers)
    d = ctx.reports.dashboard()
    assert d["total_products"] == 4 and d["total_keys"] == 1 and d["total_customers"] == 2
    assert d["allocated_activations"] == 3 and d["available_activations"] == 2
    assert d["total_sales"] == 2 and d["revenue"] == 160000 + 85000
    assert d["cost_of_sales"] == 60000 and d["gross_profit"] == 185000 and d["purchase_costs"] == 100000
    # cancelling s2 (consumed) removes revenue and shows the consumed cost as a loss
    ctx.sales.cancel_sale(s2, "refund")
    rep = ctx.reports.profit_report()
    assert rep.totals[2] == "160,000" and rep.totals[3] == "40,000" and rep.totals[4] == "20,000"
    assert rep.totals[5] == "100,000"


def test_period_filter(ctx, helpers):
    _business(ctx, helpers)
    assert ctx.reports.dashboard("2026-11-11", "2026-11-30")["revenue"] == 85000


def test_all_reports_export(ctx, helpers, tmp_path):
    _business(ctx, helpers)
    for name in ("inventory", "sales", "customers", "activations", "profit"):
        rep = ctx.reports.report(name)
        csv_path = write_csv(tmp_path / f"{name}.csv", rep)
        assert csv_path.read_text(encoding="utf-8-sig").splitlines()[0].startswith(rep.headers[0])
        pdf = write_report_pdf(tmp_path / f"{name}.pdf", rep, "Christian Joel Mtei")
        assert rep.title in PdfReader(str(pdf)).pages[0].extract_text()


def test_login_and_lockout(raw_ctx):
    raw_ctx.auth.create_admin("Admin", "Admin", PASSWORD, RECOVERY)
    raw_ctx.auth.lock()
    with pytest.raises(AuthError):
        raw_ctx.auth.login("admin", "wrong")
    raw_ctx.auth.login("ADMIN", PASSWORD)
    assert raw_ctx.auth.is_unlocked()
    for _ in range(5):
        with pytest.raises(AuthError):
            raw_ctx.auth.login("admin", "wrong")
    with pytest.raises(AuthError, match="wait"):
        raw_ctx.auth.login("admin", PASSWORD)
    actions = [a["action"] for a in raw_ctx.audit.recent()]
    assert "LOGIN_FAILED" in actions and "LOGIN" in actions


def test_weak_password_rejected(raw_ctx):
    with pytest.raises(ValidationError):
        raw_ctx.auth.create_admin("A", "a", "short", RECOVERY)


def test_recovery_when_keychain_lost(ctx, helpers, keystore):
    lid = helpers.add_key(ctx, key="RECOV-ERYKY-00001")
    keystore.clear()
    ctx.auth.lock()
    with pytest.raises(KeyStoreError):
        ctx.auth.login("admin", PASSWORD)
    with pytest.raises(AuthError):
        ctx.auth.recover_with_passphrase("wrong passphrase!!")
    ctx.auth.recover_with_passphrase(RECOVERY)
    assert ctx.inventory.reveal_key(lid) == "RECOV-ERYKY-00001"
    assert keystore.load() is not None


def test_change_password(ctx):
    ctx.auth.change_password(PASSWORD, "new password 2")
    ctx.auth.lock()
    ctx.auth.login("admin", "new password 2")
    with pytest.raises(AuthError):
        ctx.auth.change_password("wrong", "another pass 3")


def test_audit_log_append_only(ctx):
    from sqlalchemy.exc import DBAPIError

    from conftest import raw_execute
    with pytest.raises(DBAPIError):
        raw_execute(ctx, "DELETE FROM audit_log")


@pytest.mark.sqlite_only
def test_backup_verify_restore_roundtrip(ctx, helpers, tmp_path, paths):
    _business(ctx, helpers)
    lid = ctx.inventory.list_licenses()[0].id
    note = ctx.delivery_notes.list_notes()[0]
    ctx.delivery_notes.pdf_file(note.id)
    backup = ctx.backup.create_backup(tmp_path / "bk", "backup-pass-1")
    info = ctx.backup.verify_backup(backup, "backup-pass-1")
    assert info["counts"]["sales"] == 2 and info["counts"]["licenses"] == 1
    assert ctx.backup.history()[0]["verified"]
    with pytest.raises(BackupError, match="Wrong backup password"):
        ctx.backup.verify_backup(backup, "nope-nope-nope")

    # Restore onto a brand-new Mac: empty data folder, empty Keychain
    new_paths = type(paths)(root=tmp_path / "newmac", logs=tmp_path / "newlogs").ensure()
    new_ks = MemoryKeyStore()
    fresh = AppContext.open(new_paths, new_ks)
    fresh.auth.create_admin("Temp", "temp", "temp password", "temp recovery phrase")
    safety = fresh.backup.restore_backup(backup, "backup-pass-1")
    assert safety.exists()
    fresh.auth.login("admin", PASSWORD)  # original admin restored
    assert fresh.inventory.reveal_key(lid) == "PROFT-00001"
    assert len(fresh.sales.list_sales()) == 2
    assert fresh.delivery_notes.pdf_file(note.id).exists()
    assert "RESTORE" in [a["action"] for a in fresh.audit.recent()]
    fresh.db.dispose()


@pytest.mark.sqlite_only
def test_tampered_backup_rejected(ctx, tmp_path):
    backup = ctx.backup.create_backup(tmp_path, "backup-pass-1")
    data = bytearray(backup.read_bytes())
    data[-10] ^= 0xFF
    backup.write_bytes(bytes(data))
    with pytest.raises(BackupError):
        ctx.backup.verify_backup(backup, "backup-pass-1")
    bad = tmp_path / "x.bjtbackup"
    bad.write_bytes(b"hello")
    with pytest.raises(BackupError, match="not a Bejitech backup"):
        ctx.backup.verify_backup(bad, "backup-pass-1")
