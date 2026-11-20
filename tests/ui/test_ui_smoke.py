"""UI smoke tests (Qt offscreen). They open every screen and drive the main workflows."""
import pytest
from PySide6.QtWidgets import QInputDialog, QMessageBox

from bejitech.ui.dialogs.license_form import LicenseForm
from bejitech.ui.dialogs.product_form import ProductForm
from bejitech.ui.main_window import PAGES, MainWindow
from bejitech.ui.theme import STYLESHEET


@pytest.fixture
def window(qtbot, qapp, ctx, monkeypatch):
    # never block on modal message boxes during tests
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: 0))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: pytest.fail(f"warning shown: {a[2]}")))
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: pytest.fail(f"error shown: {a[2]}")))
    qapp.setStyleSheet(STYLESHEET)
    w = MainWindow(ctx)
    qtbot.addWidget(w)
    w.show()
    return w


def test_every_page_opens(window):
    for name, _, _ in PAGES:
        window.go(name)
        assert window.stack.currentWidget() is window.pages[name]


def test_product_form_adds_product(window, qtbot, ctx):
    form = ProductForm(ctx, parent=window)
    form.publisher.setCurrentText("Microsoft")
    form.category.setCurrentText("Servers")
    form.line.setCurrentText("Windows Server")
    form.version.setText("2022")
    form.edition.setText("Standard")
    form._suggest_name()
    form.price.setText("450,000")
    form._save()
    assert form.result() == 1
    p = ctx.catalogue.get_product(form.saved_id)
    assert p.display_name == "Windows Server 2022 Standard" and p.selling_price_minor == 450000
    window.go("Software Products")
    assert window.pages["Software Products"].table.model_.rowCount() == 5


def test_full_sale_workflow_through_ui(window, ctx, helpers, monkeypatch):
    form = LicenseForm(ctx, parent=window)
    form.product.setCurrentIndex(form.product.findData(helpers.product_id(ctx)))
    form.key_one.setText("UIKEY-AAAAA-BBBBB-CCCCC-DDDDD")
    form.cost.setText("30000")
    form.capacity.setValue(3)
    form._save()
    assert form.result() == 1
    cid = helpers.add_customer(ctx, "UI Customer")
    window.go("New Sale")
    page = window.pages["New Sale"]
    page.customer.setCurrentIndex(page.customer.findData(cid))
    page.product.setCurrentIndex(page.product.findData(helpers.product_id(ctx)))
    page.qty.setValue(2)
    assert "Recommended" in page.options.item(0).text()
    assert page.complete.isEnabled()
    page._complete()
    sales = ctx.sales.list_sales()
    assert len(sales) == 1 and sales[0].quantity == 2
    window.go("Delivery Notes")
    dn = window.pages["Delivery Notes"]
    assert dn.viewer.doc.pageCount() >= 1
    window.go("License Inventory")
    inv = window.pages["License Inventory"]
    inv.table.selectRow(0)
    assert inv.history.model_.rowCount() == 1
    window.go("Dashboard")
    assert window.pages["Dashboard"].cards["total_sales"].value.text() == "1"


def test_reports_tabs(window):
    window.go("Reports")
    page = window.pages["Reports"]
    for i in range(page.tabs.count()):
        page.tabs.setCurrentIndex(i)
        assert page.report is not None


def test_settings_save(window, ctx):
    window.go("Settings")
    page = window.pages["Settings"]
    page.fields["seller.phone"].setText("+255 700 000 000")
    page._save()
    assert ctx.settings.get("seller.phone") == "+255 700 000 000"


def test_edit_dialog_allows_product_change_until_sold(window, ctx, helpers):
    lid = helpers.add_key(ctx, key="EDITU-IKEY0-00001", capacity=2)
    win = helpers.product_id(ctx, "Windows 11 Pro")
    form = LicenseForm(ctx, license_id=lid, parent=window)
    assert form.product.isEnabled()
    form.product.setCurrentIndex(form.product.findData(win))
    form._save()
    assert form.result() == 1
    assert ctx.inventory.get_license(lid).product_id == win
    from bejitech.core.dto import SaleInput
    ctx.sales.create_sale(SaleInput(helpers.add_customer(ctx), win, 1, 1000, "CASH", "2026-11-18"))
    locked = LicenseForm(ctx, license_id=lid, parent=window)
    assert not locked.product.isEnabled()
    assert "locked" in locked.type_label.text()


def test_licence_type_field_in_edit_and_add(window, ctx, helpers):
    mak = next(t["id"] for t in ctx.catalogue.list_license_types() if t["code"] == "MAK")
    lid = helpers.add_key(ctx, key="TYPEU-IKEY0-00001", capacity=2)
    form = LicenseForm(ctx, license_id=lid, parent=window)
    assert form.ltype.isEnabled() and form.ltype.currentText() == "Retail"
    form.ltype.setCurrentIndex(form.ltype.findData(mak))
    form._save()
    assert form.result() == 1
    assert ctx.catalogue.get_product(ctx.inventory.get_license(lid).product_id).license_type_id == mak
    add = LicenseForm(ctx, parent=window)
    add.product.setCurrentIndex(add.product.findData(helpers.product_id(ctx, "Windows 11 Pro")))
    add.ltype.setCurrentIndex(add.ltype.findData(mak))
    assert add.capacity.value() == 5  # MAK default activations
    add.key_one.setText("TYPEU-IKEY0-00002")
    add.cost.setText("1000")
    add._save()
    assert add.result() == 1
    new = [l for l in ctx.inventory.list_licenses() if l.key_suffix == "00002"][0]
    assert ctx.catalogue.get_product(new.product_id).license_type_id == mak
