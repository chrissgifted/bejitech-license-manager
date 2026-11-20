from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QPlainTextEdit, QPushButton, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

from bejitech.core.dto import ProductInput
from bejitech.ui.widgets.common import MoneyEdit, run_action, show_error

PLATFORMS = ["Windows", "macOS", "Windows & macOS", "Linux", "Cross-platform", "Android", "iOS"]


def _combo(items, current="", editable=True) -> QComboBox:
    c = QComboBox()
    c.setEditable(editable)
    c.addItems(items)
    if current:
        c.setCurrentText(current)
    return c


class ProductForm(QDialog):
    def __init__(self, ctx, product_id: int | None = None, parent=None):
        super().__init__(parent)
        self.ctx, self.product_id, self.saved_id = ctx, product_id, None
        self.pending_logo: str | None = None
        self.remove_logo = False
        self.setWindowTitle("Edit product" if product_id else "Add product")
        self.setMinimumSize(640, 560)
        cat = ctx.catalogue
        p = cat.get_product(product_id) if product_id else None
        self._auto_name = not (p and p.display_name)
        lay = QVBoxLayout(self)
        tabs = QTabWidget()
        lay.addWidget(tabs)

        # General
        g = QWidget()
        f = QFormLayout(g)
        self.publisher = _combo(cat.list_publishers(), p.publisher if p else "Microsoft")
        self.category = _combo(cat.list_categories(), p.category if p else "")
        self.line = _combo(cat.list_product_lines(), p.product_line if p else "")
        self.line.setPlaceholderText("e.g. Microsoft Office, Windows, Visio")
        self.version = QLineEdit(p.version if p else "")
        self.version.setPlaceholderText("e.g. 2024")
        self.edition = QLineEdit(p.edition if p else "")
        self.edition.setPlaceholderText("e.g. Professional Plus")
        self.platform = _combo(PLATFORMS, p.platform if p else "Windows")
        self.ltype = QComboBox()
        for t in cat.list_license_types():
            self.ltype.addItem(t["name"], t["id"])
        if p:
            self.ltype.setCurrentIndex(self.ltype.findData(p.license_type_id))
        self.name = QLineEdit(p.display_name if p else "")
        self.sku = QLineEdit(p.sku_code or "" if p else "")
        self.low = QSpinBox()
        self.low.setRange(0, 100000)
        self.low.setValue(p.low_stock_threshold if p else int(ctx.settings.get("inventory.default_low_stock", "3")))
        f.addRow("Publisher *", self.publisher)
        f.addRow("Category *", self.category)
        f.addRow("Product *", self.line)
        f.addRow("Version *", self.version)
        f.addRow("Edition *", self.edition)
        f.addRow("Platform", self.platform)
        f.addRow("Licence type *", self.ltype)
        f.addRow("Display name", self.name)
        f.addRow("SKU / internal code", self.sku)
        f.addRow("Low-stock alert below", self.low)
        tabs.addTab(g, "General")
        for w in (self.line, self.version, self.edition):
            (w.lineEdit() if isinstance(w, QComboBox) else w).textEdited.connect(self._suggest_name)
        self.name.textEdited.connect(lambda _: setattr(self, "_auto_name", False))

        # Pricing
        pr = QWidget()
        f2 = QFormLayout(pr)
        self.cost_currency = _combo(["TZS", "USD"], p.purchase_currency if p else "TZS", editable=False)
        self.cost = MoneyEdit(self.cost_currency.currentText())
        self.cost_currency.currentTextChanged.connect(self.cost.set_currency)
        self.price = MoneyEdit("TZS")
        if p:
            self.cost.set_value(p.purchase_price_minor)
            self.price.set_value(p.selling_price_minor)
        row = QHBoxLayout()
        row.addWidget(self.cost, 1)
        row.addWidget(self.cost_currency)
        f2.addRow("Typical purchase price", row)
        f2.addRow("Selling price (TZS)", self.price)
        note = QLabel("The actual cost of each key is recorded when you add it to inventory.")
        note.setObjectName("Muted")
        f2.addRow(note)
        tabs.addTab(pr, "Pricing")

        # Download & instructions
        d = QWidget()
        f3 = QFormLayout(d)
        self.url = QLineEdit(p.download_url or "" if p else "")
        self.url.setPlaceholderText("https://…  (prefer official, verified sources)")
        self.label = QLineEdit(p.download_label or "" if p else "")
        self.label.setPlaceholderText("Left blank → “Download <product name>”")
        self.verified = QCheckBox("I have checked this link points to an authorised, safe download")
        self.verified.setChecked(bool(p and p.download_url_verified))
        self.install = QPlainTextEdit(p.installation_instructions or "" if p else "")
        self.activate = QPlainTextEdit(p.activation_instructions or "" if p else "")
        f3.addRow("Download URL", self.url)
        f3.addRow("Link text", self.label)
        f3.addRow("", self.verified)
        f3.addRow("Installation instructions", self.install)
        f3.addRow("Activation instructions", self.activate)
        tabs.addTab(d, "Download && Instructions")

        # Logo
        lg = QWidget()
        v = QVBoxLayout(lg)
        self.preview = QLabel("No logo")
        self.preview.setFixedSize(180, 180)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setStyleSheet("background: white; border: 1px dashed #C5CCD8; border-radius: 8px;")
        v.addWidget(self.preview)
        hb = QHBoxLayout()
        choose = QPushButton("Choose image…")
        choose.clicked.connect(self._choose_logo)
        rm = QPushButton("Remove logo")
        rm.clicked.connect(self._remove_logo)
        hb.addWidget(choose)
        hb.addWidget(rm)
        hb.addStretch(1)
        v.addLayout(hb)
        hint = QLabel("Use only logos you are allowed to use. PNG or JPG, up to 5 MB. "
                      "The delivery note colour adapts to the logo.")
        hint.setWordWrap(True)
        hint.setObjectName("Muted")
        v.addWidget(hint)
        v.addStretch(1)
        tabs.addTab(lg, "Logo")
        if p and p.logo_path:
            f = ctx.catalogue.logo_file(p.logo_path)
            if f:
                self._show_logo(str(f))

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Save).setObjectName("Primary")
        bb.accepted.connect(self._save)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _suggest_name(self, *_):
        if self._auto_name:
            parts = [self.line.currentText().strip(), self.version.text().strip(), self.edition.text().strip()]
            self.name.setText(" ".join(x for x in parts if x))

    def _show_logo(self, path: str):
        pm = QPixmap(path)
        if not pm.isNull():
            self.preview.setPixmap(pm.scaled(170, 170, Qt.AspectRatioMode.KeepAspectRatio,
                                             Qt.TransformationMode.SmoothTransformation))

    def _choose_logo(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose product logo", "", "Images (*.png *.jpg *.jpeg)")
        if path:
            self.pending_logo, self.remove_logo = path, False
            self._show_logo(path)

    def _remove_logo(self):
        self.pending_logo, self.remove_logo = None, True
        self.preview.clear()
        self.preview.setText("No logo")

    def _save(self):
        try:
            data = ProductInput(
                id=self.product_id, publisher_name=self.publisher.currentText(),
                category_name=self.category.currentText(), product_line_name=self.line.currentText(),
                version=self.version.text(), edition=self.edition.text(), platform=self.platform.currentText(),
                license_type_id=self.ltype.currentData(), display_name=self.name.text(), sku_code=self.sku.text(),
                purchase_price_minor=self.cost.value_minor(), purchase_currency=self.cost_currency.currentText(),
                selling_price_minor=self.price.value_minor(), download_url=self.url.text(),
                download_label=self.label.text(), download_url_verified=self.verified.isChecked(),
                installation_instructions=self.install.toPlainText(),
                activation_instructions=self.activate.toPlainText(), low_stock_threshold=self.low.value())
        except Exception as exc:  # noqa: BLE001
            return show_error(self, exc)
        pid = run_action(self, self.ctx.catalogue.save_product, data)
        if not pid:
            return
        if self.pending_logo:
            run_action(self, self.ctx.catalogue.set_logo, pid, self.pending_logo)
        elif self.remove_logo:
            run_action(self, self.ctx.catalogue.set_logo, pid, None)
        self.saved_id = pid
        self.accept()
