from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QFormLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QSpinBox,
    QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from bejitech import APP_NAME, __version__
from bejitech.core.money import parse_rate
from bejitech.core.timeutil import display_datetime
from bejitech.ui.views.base import Page
from bejitech.ui.widgets.common import (
    DataTable, PageHeader, SearchBox, info, page_layout, primary_button, run_action, show_error,
)
from bejitech.ui.widgets.pdf_tools import reveal_in_finder


def _pw() -> QLineEdit:
    e = QLineEdit()
    e.setEchoMode(QLineEdit.EchoMode.Password)
    return e


class SettingsPage(Page):
    title = "Settings"

    def __init__(self, ctx, main=None):
        super().__init__(ctx, main)
        lay = page_layout(self)
        lay.addWidget(PageHeader("Settings"))
        self.tabs = QTabWidget()
        lay.addWidget(self.tabs, 1)
        self.fields: dict[str, QWidget] = {}

        biz = QWidget()
        f = QFormLayout(biz)
        for key, label in (("seller.name", "Seller name"), ("seller.business_name", "Business name"),
                           ("seller.phone", "Phone"), ("seller.email", "Email"), ("seller.address", "Address")):
            self.fields[key] = QLineEdit()
            f.addRow(label, self.fields[key])
        f.addRow(QLabel("These details appear on new delivery notes. Notes already issued keep the details they "
                        "were issued with."))
        self.tabs.addTab(biz, "Business")

        sales = QWidget()
        f = QFormLayout(sales)
        self.fields["currency.usd_rate"] = QLineEdit()
        f.addRow("Default currency", QLabel("TZS (Tanzanian Shillings)"))
        f.addRow("USD → TZS exchange rate", self.fields["currency.usd_rate"])
        self.fields["inventory.default_low_stock"] = QSpinBox()
        self.fields["inventory.default_low_stock"].setRange(0, 10000)
        f.addRow("Default low-stock level for new products", self.fields["inventory.default_low_stock"])
        self.tabs.addTab(sales, "Sales && currency")

        lt = QWidget()
        v = QVBoxLayout(lt)
        v.addWidget(QLabel("Defaults applied to newly added keys. Turn on only when the licence terms allow it."))
        self.types = QTableWidget(0, 4)
        self.types.setHorizontalHeaderLabels(["Licence type", "Several customers per key", "Reassignable after cancellation",
                                              "Default activations"])
        self.types.horizontalHeader().setStretchLastSection(True)
        self.types.verticalHeader().setVisible(False)
        v.addWidget(self.types)
        self.tabs.addTab(lt, "Licence types")

        dn = QWidget()
        f = QFormLayout(dn)
        self.fields["delivery.include_signature"] = QCheckBox("Show the signature section on delivery notes")
        self.fields["delivery.footer"] = QPlainTextEdit()
        self.fields["delivery.footer"].setFixedHeight(70)
        f.addRow("", self.fields["delivery.include_signature"])
        f.addRow("Footer text", self.fields["delivery.footer"])
        self.tabs.addTab(dn, "Delivery notes")

        sec = QWidget()
        f = QFormLayout(sec)
        self.fields["security.autolock_minutes"] = QSpinBox()
        self.fields["security.autolock_minutes"].setRange(1, 240)
        self.fields["security.clipboard_clear_seconds"] = QSpinBox()
        self.fields["security.clipboard_clear_seconds"].setRange(10, 600)
        f.addRow("Lock after inactivity (minutes)", self.fields["security.autolock_minutes"])
        f.addRow("Clear copied keys from clipboard after (seconds)", self.fields["security.clipboard_clear_seconds"])
        self.ks_label = QLabel()
        f.addRow("Encryption key stored in", self.ks_label)
        self.cur, self.new1, self.new2 = _pw(), _pw(), _pw()
        f.addRow(QLabel("<b>Change password</b>"))
        f.addRow("Current password", self.cur)
        f.addRow("New password", self.new1)
        f.addRow("Confirm new password", self.new2)
        cp = QPushButton("Change password")
        cp.clicked.connect(self._change_pw)
        rp = QPushButton("Change recovery passphrase…")
        rp.clicked.connect(self._change_recovery)
        hb = QHBoxLayout()
        hb.addWidget(cp)
        hb.addWidget(rp)
        hb.addStretch(1)
        f.addRow("", hb)
        self.tabs.addTab(sec, "Security")

        au = QWidget()
        v = QVBoxLayout(au)
        self.audit_search = SearchBox("Search actions…")
        self.audit_search.search.connect(lambda _: self._load_audit())
        v.addWidget(self.audit_search)
        self.audit = DataTable(["When", "User", "Action", "Item", "Details"], stretch_col=4)
        v.addWidget(self.audit)
        self.tabs.addTab(au, "Audit log")
        self.tabs.currentChanged.connect(lambda i: self._load_audit() if self.tabs.tabText(i) == "Audit log" else None)

        ab = QWidget()
        v = QVBoxLayout(ab)
        v.addWidget(QLabel(f"<b>{APP_NAME}</b> version {__version__}"))
        self.data_label = QLabel()
        self.data_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        v.addWidget(self.data_label)
        sf = QPushButton("Show data folder")
        sf.clicked.connect(lambda: reveal_in_finder(ctx.paths.database))
        v.addWidget(sf, 0, Qt.AlignmentFlag.AlignLeft)
        v.addWidget(QLabel("Built with Python, Qt for Python (PySide6, LGPL), SQLite, SQLAlchemy, ReportLab, "
                           "cryptography and argon2-cffi."))
        v.addStretch(1)
        self.tabs.addTab(ab, "About")

        save = primary_button("Save settings", self._save)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(save)
        lay.addLayout(row)

    def refresh(self):
        st = self.ctx.settings.all()
        for key, w in self.fields.items():
            val = st.get(key, "")
            if isinstance(w, QLineEdit):
                w.setText(val)
            elif isinstance(w, QSpinBox):
                w.setValue(int(val or 0))
            elif isinstance(w, QCheckBox):
                w.setChecked(val == "1")
            elif isinstance(w, QPlainTextEdit):
                w.setPlainText(val)
        types = self.ctx.catalogue.list_license_types()
        self.types.setRowCount(len(types))
        for r, t in enumerate(types):
            it = QTableWidgetItem(t["name"])
            it.setData(Qt.ItemDataRole.UserRole, t["id"])
            it.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.types.setItem(r, 0, it)
            for c, key in ((1, "allows_multiple_customers"), (2, "reassignable")):
                cb = QTableWidgetItem()
                cb.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
                cb.setCheckState(Qt.CheckState.Checked if t[key] else Qt.CheckState.Unchecked)
                self.types.setItem(r, c, cb)
            cap = QTableWidgetItem(str(t["default_capacity"]))
            self.types.setItem(r, 3, cap)
        self.types.resizeColumnsToContents()
        self.ks_label.setText(self.ctx.keystore.describe())
        self.data_label.setText(f"Data folder: {self.ctx.paths.root}")

    def _save(self):
        values = {}
        for key, w in self.fields.items():
            if isinstance(w, QLineEdit):
                values[key] = w.text()
            elif isinstance(w, QSpinBox):
                values[key] = str(w.value())
            elif isinstance(w, QCheckBox):
                values[key] = "1" if w.isChecked() else "0"
            elif isinstance(w, QPlainTextEdit):
                values[key] = w.toPlainText()
        try:
            values["currency.usd_rate"] = str(parse_rate(values["currency.usd_rate"]))
            for r in range(self.types.rowCount()):
                cap = int(self.types.item(r, 3).text())
                self.ctx.catalogue.update_license_type(
                    self.types.item(r, 0).data(Qt.ItemDataRole.UserRole),
                    self.types.item(r, 1).checkState() == Qt.CheckState.Checked,
                    self.types.item(r, 2).checkState() == Qt.CheckState.Checked, cap)
        except Exception as exc:  # noqa: BLE001
            return show_error(self, exc if not isinstance(exc, ValueError) else "Default activations must be a number.")
        try:
            self.ctx.settings.update(values)
        except Exception as exc:  # noqa: BLE001
            return show_error(self, exc)
        if self.main:
            self.main.apply_security_settings()
        info(self, "Settings saved.")

    def _change_pw(self):
        if self.new1.text() != self.new2.text():
            return show_error(self, "The new passwords do not match.")
        try:
            self.ctx.auth.change_password(self.cur.text(), self.new1.text())
        except Exception as exc:  # noqa: BLE001
            return show_error(self, exc)
        for w in (self.cur, self.new1, self.new2):
            w.clear()
        info(self, "Password changed.")

    def _change_recovery(self):
        pw, ok = QInputDialog.getText(self, "Recovery passphrase", "Current password:", QLineEdit.EchoMode.Password)
        if not ok:
            return
        p1, ok = QInputDialog.getText(self, "Recovery passphrase", "New recovery passphrase (12+ characters):",
                                      QLineEdit.EchoMode.Password)
        if not ok:
            return
        p2, ok = QInputDialog.getText(self, "Recovery passphrase", "Confirm new recovery passphrase:",
                                      QLineEdit.EchoMode.Password)
        if not ok:
            return
        if p1 != p2:
            return show_error(self, "The passphrases do not match.")
        try:
            self.ctx.auth.change_recovery_passphrase(pw, p1)
        except Exception as exc:  # noqa: BLE001
            return show_error(self, exc)
        info(self, "Recovery passphrase changed. Write the new one down and keep it safe.")

    def _load_audit(self):
        self.audit.set_rows([(i, [display_datetime(a["occurred_at"]), a["user"], a["action"], a["entity"],
                                  a["details"]]) for i, a in enumerate(self.ctx.audit.recent(1000, self.audit_search.text()))])
