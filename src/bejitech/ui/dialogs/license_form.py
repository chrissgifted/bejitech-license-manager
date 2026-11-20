from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QPlainTextEdit, QSpinBox, QVBoxLayout,
)

from bejitech.core.dto import LicenseInput
from bejitech.core.money import convert_to_tzs, format_money
from bejitech.ui.widgets.common import DateEdit, MoneyEdit, info, run_action, show_error


class LicenseForm(QDialog):
    """Add one or several keys, or edit an existing key's details (the key itself never changes)."""

    def __init__(self, ctx, license_id: int | None = None, product_id: int | None = None, parent=None):
        super().__init__(parent)
        self.ctx, self.license_id = ctx, license_id
        editing = license_id is not None
        self.setWindowTitle("Edit licence" if editing else "Add licence keys")
        self.setMinimumWidth(560)
        lic = ctx.inventory.get_license(license_id) if editing else None
        lay = QVBoxLayout(self)
        f = QFormLayout()

        self.product = QComboBox()
        self.types = {t["id"]: t for t in ctx.catalogue.list_license_types()}
        self.products = {p.id: p for p in ctx.catalogue.list_products()}
        for p in self.products.values():
            self.product.addItem(p.display_name, p.id)
        if lic:
            self.product.addItem(lic.product_name, lic.product_id) if lic.product_id not in self.products else None
            self.product.setCurrentIndex(self.product.findData(lic.product_id))
            self.product_changeable = ctx.inventory.can_change_product(license_id)
            self.product.setEnabled(self.product_changeable)
        elif product_id:
            self.product.setCurrentIndex(max(0, self.product.findData(product_id)))
        f.addRow("Product *", self.product)
        self.ltype = QComboBox()
        for t in self.types.values():
            self.ltype.addItem(t["name"], t["id"])
        self.ltype.setEnabled(not lic or self.product_changeable)
        f.addRow("Licence type *", self.ltype)
        self.type_label = QLabel()
        self.type_label.setObjectName("Muted")
        self.type_label.setWordWrap(True)
        f.addRow("", self.type_label)

        if editing:
            k = QLabel(lic.masked_key)
            k.setObjectName("KeyLabel")
            f.addRow("Licence key", k)
            f.addRow("Reference", QLabel(lic.inventory_ref))
        else:
            self.bulk = QCheckBox("Add several keys with the same details (one key per line)")
            self.key_one = QLineEdit()
            self.key_one.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
            self.key_one.setPlaceholderText("XXXXX-XXXXX-XXXXX-XXXXX-XXXXX")
            self.key_many = QPlainTextEdit()
            self.key_many.setPlaceholderText("One licence key per line")
            self.key_many.setVisible(False)
            self.bulk.toggled.connect(lambda on: (self.key_many.setVisible(on), self.key_one.setVisible(not on)))
            f.addRow("", self.bulk)
            f.addRow("Licence key *", self.key_one)
            f.addRow("", self.key_many)

        self.supplier = QComboBox()
        self.supplier.setEditable(True)
        self.supplier.addItems([""] + ctx.inventory.list_suppliers())
        self.supplier.setCurrentText(lic.supplier or "" if lic else "")
        f.addRow("Supplier", self.supplier)

        if not editing:
            self.purchase_date = DateEdit()
            self.currency = QComboBox()
            self.currency.addItems(["TZS", "USD"])
            self.cost = MoneyEdit("TZS")
            self.rate = QLineEdit(ctx.settings.get("currency.usd_rate", "2650"))
            self.rate.setFixedWidth(100)
            self.tzs_label = QLabel()
            self.tzs_label.setObjectName("Muted")
            row = QHBoxLayout()
            row.addWidget(self.cost, 1)
            row.addWidget(self.currency)
            self.rate_lab = QLabel("@ rate")
            row.addWidget(self.rate_lab)
            row.addWidget(self.rate)
            f.addRow("Purchase date *", self.purchase_date)
            f.addRow("Cost per key *", row)
            f.addRow("", self.tzs_label)
            self.capacity = QSpinBox()
            self.capacity.setRange(1, 100000)
            f.addRow("Permitted activations *", self.capacity)
            self.currency.currentTextChanged.connect(self._currency_changed)
            self.cost.value_changed.connect(self._update_tzs)
            self.rate.textChanged.connect(self._update_tzs)
            self.product.currentIndexChanged.connect(self._product_changed)

        self.multi = QCheckBox("Licence terms allow allocating this key to more than one customer")
        self.reassign = QCheckBox("Activations may be reassigned to another customer after cancellation")
        f.addRow("", self.multi)
        f.addRow("", self.reassign)
        self.expiry = DateEdit(lic.expiration_date if lic else None, allow_empty=True)
        f.addRow("Expiry date", self.expiry)
        self.restrictions = QLineEdit(lic.restrictions or "" if lic else "")
        self.restrictions.setPlaceholderText("e.g. Windows only, Tanzania region, one PC")
        f.addRow("Restrictions", self.restrictions)
        self.notes = QPlainTextEdit(lic.notes or "" if lic else "")
        self.notes.setFixedHeight(60)
        f.addRow("Notes", self.notes)
        lay.addLayout(f)
        if lic:
            self.multi.setChecked(lic.allows_multiple_customers)
            self.reassign.setChecked(lic.reassignable)
            self._show_type()
            self.product.currentIndexChanged.connect(self._edit_product_changed)
            self.ltype.currentIndexChanged.connect(self._type_changed)
        else:
            self.ltype.currentIndexChanged.connect(self._type_changed)
            self._product_changed()
            self._currency_changed("TZS")

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Save).setObjectName("Primary")
        bb.accepted.connect(self._save)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _show_type(self):
        """Show the selected product's licence type in the Licence type box."""
        p = self.products.get(self.product.currentData())
        if p:
            self.ltype.blockSignals(True)
            self.ltype.setCurrentIndex(self.ltype.findData(p.license_type_id))
            self.ltype.blockSignals(False)
        self._hint()

    def _hint(self):
        if self.license_id and not getattr(self, "product_changeable", True):
            text = ("This key has already been sold, so its product and licence type are locked. Cancel those "
                    "sales with the activations returned to stock, or disable the key and add it again.")
        else:
            p = self.products.get(self.product.currentData())
            if p and self.ltype.currentData() != p.license_type_id:
                text = (f"The key will be filed under “{p.display_name}” as {self.ltype.currentText()}. "
                        "If that product does not exist with this licence type yet, it is created with the "
                        "same prices, download link and instructions.")
            else:
                text = ""
        self.type_label.setText(text)
        self.type_label.setVisible(bool(text))
        if self.isVisible():
            self.adjustSize()

    def _apply_type_defaults(self, type_id):
        t = self.types.get(type_id, {})
        self.multi.setChecked(bool(t.get("allows_multiple_customers")))
        self.reassign.setChecked(bool(t.get("reassignable")))
        return t

    def _type_changed(self, *_):
        t = self._apply_type_defaults(self.ltype.currentData())
        if not self.license_id and t:
            self.capacity.setValue(int(t.get("default_capacity", 1)))
        self._hint()

    def _edit_product_changed(self, *_):
        p = self.products.get(self.product.currentData())
        if p:
            self._apply_type_defaults(p.license_type_id)
        self._show_type()

    def _product_changed(self, *_):
        p = self.products.get(self.product.currentData())
        self._show_type()
        if not p:
            return
        t = self.types.get(p.license_type_id, {})
        self.multi.setChecked(bool(t.get("allows_multiple_customers")))
        self.reassign.setChecked(bool(t.get("reassignable")))
        self.capacity.setValue(int(t.get("default_capacity", 1)))
        if p.purchase_price_minor and not self.cost.text():
            self.currency.setCurrentText(p.purchase_currency)
            self.cost.set_currency(p.purchase_currency)
            self.cost.set_value(p.purchase_price_minor)

    def _currency_changed(self, cur):
        self.cost.set_currency(cur)
        usd = cur == "USD"
        self.rate.setVisible(usd)
        self.rate_lab.setVisible(usd)
        self._update_tzs()

    def _update_tzs(self, *_):
        if self.currency.currentText() != "USD":
            self.tzs_label.setText("")
            return
        try:
            tzs = convert_to_tzs(self.cost.value_minor(), "USD", self.rate.text())
            self.tzs_label.setText(f"= {format_money(tzs)} per key")
        except Exception:  # noqa: BLE001
            self.tzs_label.setText("Enter a valid amount and rate")

    def _save(self):
        if self.license_id:
            ok = run_action(self, self._update)
            if ok:
                self.accept()
            return
        try:
            tmpl = LicenseInput(
                product_id=self.product.currentData(), license_key="", purchase_date=self.purchase_date.iso(),
                purchase_cost_minor=self.cost.value_minor(), permitted_capacity=self.capacity.value(),
                purchase_currency=self.currency.currentText(),
                exchange_rate_to_tzs=self.rate.text() if self.currency.currentText() == "USD" else "1",
                supplier_name=self.supplier.currentText(), allows_multiple_customers=self.multi.isChecked(),
                reassignable=self.reassign.isChecked(), restrictions=self.restrictions.text(),
                expiration_date=self.expiry.iso(), notes=self.notes.toPlainText())
        except Exception as exc:  # noqa: BLE001
            return show_error(self, exc)
        if tmpl.product_id is None:
            return show_error(self, "Please add a product first.")
        p = self.products.get(tmpl.product_id)
        if p and self.ltype.currentData() != p.license_type_id:
            pid = run_action(self, self.ctx.catalogue.variant_for_type, tmpl.product_id, self.ltype.currentData())
            if not pid:
                return
            tmpl.product_id = pid
        if self.bulk.isChecked():
            keys = self.key_many.toPlainText().splitlines()
            ids = run_action(self, self.ctx.inventory.add_licenses_bulk, keys, tmpl)
            if ids:
                info(self, f"{len(ids)} licence keys added.")
                self.accept()
        else:
            tmpl.license_key = self.key_one.text()
            if run_action(self, self.ctx.inventory.add_license, tmpl):
                self.accept()

    def _update(self):
        self.ctx.inventory.update_license(
            self.license_id, supplier_name=self.supplier.currentText(), restrictions=self.restrictions.text(),
            expiration_date=self.expiry.iso(), notes=self.notes.toPlainText(),
            allows_multiple_customers=self.multi.isChecked(), reassignable=self.reassign.isChecked(),
            product_id=self.product.currentData(), license_type_id=self.ltype.currentData())
        return True
