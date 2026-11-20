from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QCompleter, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QSpinBox, QVBoxLayout,
)

from bejitech.core.dto import SaleInput
from bejitech.core.enums import PaymentMethod
from bejitech.core.money import format_money
from bejitech.ui.dialogs.customer_form import CustomerForm
from bejitech.ui.views.base import Page
from bejitech.ui.widgets.common import (
    Card, DateEdit, MoneyEdit, PageHeader, page_layout, primary_button, run_action, show_error,
)


class NewSalePage(Page):
    title = "New Sale"

    def __init__(self, ctx, main=None):
        super().__init__(ctx, main)
        self.rec = None
        lay = page_layout(self)
        self.header = PageHeader("New Sale", "Customer → product → recommended key → payment → delivery note")
        lay.addWidget(self.header)
        cols = QHBoxLayout()
        left, right = QVBoxLayout(), QVBoxLayout()
        cols.addLayout(left, 3)
        cols.addLayout(right, 2)
        lay.addLayout(cols, 1)

        c1 = Card("1  Customer")
        row = QHBoxLayout()
        self.customer = QComboBox()
        self.customer.setEditable(True)
        self.customer.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.customer.lineEdit().setPlaceholderText("Type name, phone or email…")
        self.customer.currentIndexChanged.connect(self._recalc)
        row.addWidget(self.customer, 1)
        nb = QPushButton("+ New customer")
        nb.clicked.connect(self._new_customer)
        row.addWidget(nb)
        c1.body.addLayout(row)
        self.customer_info = QLabel("")
        self.customer_info.setObjectName("Muted")
        c1.body.addWidget(self.customer_info)
        left.addWidget(c1)

        c2 = Card("2  Product and quantity")
        f2 = QFormLayout()
        self.product = QComboBox()
        self.product.currentIndexChanged.connect(self._product_changed)
        self.qty = QSpinBox()
        self.qty.setRange(1, 10000)
        self.qty.valueChanged.connect(self._recalc)
        f2.addRow("Product", self.product)
        f2.addRow("Activations", self.qty)
        c2.body.addLayout(f2)
        self.stock_info = QLabel("")
        self.stock_info.setObjectName("Muted")
        c2.body.addWidget(self.stock_info)
        left.addWidget(c2)

        c3 = Card("3  Licence key")
        self.options = QListWidget()
        self.options.setObjectName("Plain")
        self.options.itemSelectionChanged.connect(self._update_summary)
        c3.body.addWidget(self.options)
        self.after = QLabel("")
        self.after.setWordWrap(True)
        c3.body.addWidget(self.after)
        left.addWidget(c3, 1)

        c4 = Card("4  Price and payment")
        f4 = QFormLayout()
        self.price = MoneyEdit("TZS")
        self.discount = MoneyEdit("TZS")
        self.price.value_changed.connect(self._update_summary)
        self.discount.value_changed.connect(self._update_summary)
        self.total = QLabel("TZS 0")
        self.total.setObjectName("StatValue")
        self.payment = QComboBox()
        for m in PaymentMethod:
            self.payment.addItem(m.label, m.value)
        self.payment.setCurrentIndex(self.payment.findData("MOBILE_MONEY"))
        self.pay_ref = QLineEdit()
        self.pay_ref.setPlaceholderText("e.g. M-Pesa / bank transaction ID")
        self.date = DateEdit()
        self.notes = QLineEdit()
        f4.addRow("Unit price (TZS)", self.price)
        f4.addRow("Discount (TZS)", self.discount)
        f4.addRow("Total", self.total)
        f4.addRow("Payment method", self.payment)
        f4.addRow("Payment reference", self.pay_ref)
        f4.addRow("Sale date", self.date)
        f4.addRow("Notes", self.notes)
        c4.body.addLayout(f4)
        right.addWidget(c4)
        self.complete = primary_button("Complete sale and create delivery note", self._complete)
        self.complete.setMinimumHeight(40)
        right.addWidget(self.complete)
        right.addStretch(1)

    # ---------- data ----------
    def refresh(self, select_customer: int | None = None):
        cur_c = select_customer or self.customer.currentData()
        self.customer.blockSignals(True)
        self.customer.clear()
        self.customers = {c.id: c for c in self.ctx.customers.list()}
        for c in self.customers.values():
            self.customer.addItem(c.label, c.id)
        comp = QCompleter([self.customer.itemText(i) for i in range(self.customer.count())], self)
        comp.setFilterMode(Qt.MatchFlag.MatchContains)
        comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.customer.setCompleter(comp)
        self.customer.setCurrentIndex(self.customer.findData(cur_c) if cur_c else -1)
        self.customer.blockSignals(False)
        cur_p = self.product.currentData()
        self.product.blockSignals(True)
        self.product.clear()
        self.products = {p.id: p for p in self.ctx.catalogue.list_products()}
        for p in self.products.values():
            self.product.addItem(f"{p.display_name}  ({p.available_activations} available)", p.id)
        self.product.setCurrentIndex(max(0, self.product.findData(cur_p)))
        self.product.blockSignals(False)
        self.header.subtitle.setText("Next reference is assigned when the sale is saved.")
        self._product_changed()

    def _product_changed(self, *_):
        p = self.products.get(self.product.currentData()) if hasattr(self, "products") else None
        if p:
            self.price.set_value(p.selling_price_minor)
            self.stock_info.setText(f"In stock: {p.available_activations} activation(s) across {p.total_keys} key(s)")
        self._recalc()

    def _recalc(self, *_):
        cid = self.customer.currentData()
        c = self.customers.get(cid) if cid else None
        self.customer_info.setText(
            f"✓ {c.customer_ref} · {c.purchases} previous purchase(s)" if c else "Choose or add a customer.")
        self.options.clear()
        self.rec = None
        pid = self.product.currentData()
        if not (cid and pid):
            self._update_summary()
            return
        self.rec = run_action(self, self.ctx.allocation.recommend, pid, self.qty.value(), cid, busy=False)
        if not self.rec:
            return
        if self.rec.plan and self.rec.is_possible:
            text = " + ".join(f"{o.inventory_ref} ({o.masked_key[-5:]}) ×{o.take}, {o.remaining} left" for o in self.rec.plan)
            it = QListWidgetItem(f"★ Recommended: {text}\n    {self.rec.plan[0].reason}")
            it.setData(Qt.ItemDataRole.UserRole, [(o.license_id, o.take) for o in self.rec.plan])
            self.options.addItem(it)
            for o in self.rec.alternatives:
                it = QListWidgetItem(f"○ {o.inventory_ref} ({o.masked_key[-5:]}): {o.remaining} left"
                                     + (f", expires {o.expiration_date}" if o.expiration_date else ""))
                it.setData(Qt.ItemDataRole.UserRole, [(o.license_id, self.qty.value())])
                self.options.addItem(it)
            self.options.setCurrentRow(0)
        else:
            it = QListWidgetItem(f"✕ Not enough activations available for this customer: "
                                 f"{self.rec.total_available} available, {self.qty.value()} requested. "
                                 "Add licence keys in License Inventory.")
            it.setFlags(Qt.ItemFlag.NoItemFlags)
            self.options.addItem(it)
        self._update_summary()

    def _plan(self):
        it = self.options.currentItem()
        return it.data(Qt.ItemDataRole.UserRole) if it else None

    def _update_summary(self, *_):
        qty = self.qty.value()
        price = self.price.value_minor(silent=True)
        disc = self.discount.value_minor(silent=True)
        total = qty * price - disc
        self.total.setText(format_money(total) if total >= 0 else "Discount too large")
        plan = self._plan()
        if plan and self.rec:
            by_id = {o.license_id: o for o in self.rec.plan + self.rec.alternatives}
            parts = []
            for lid, take in plan:
                o = by_id.get(lid)
                if o:
                    left = o.remaining - take
                    parts.append(f"{o.inventory_ref} will have {left} activation(s) left"
                                 + (" (fully allocated)" if left == 0 else ""))
            self.after.setText("After this sale: " + "; ".join(parts))
        else:
            self.after.setText("")
        self.complete.setEnabled(bool(plan) and total >= 0)

    # ---------- actions ----------
    def _new_customer(self):
        d = CustomerForm(self.ctx, parent=self)
        if d.exec():
            self.refresh(select_customer=d.saved_id)

    def _complete(self):
        try:
            data = SaleInput(customer_id=self.customer.currentData(), product_id=self.product.currentData(),
                             quantity=self.qty.value(), unit_price_minor=self.price.value_minor(),
                             discount_minor=self.discount.value_minor(), payment_method=self.payment.currentData(),
                             payment_reference=self.pay_ref.text(), sale_date=self.date.iso(),
                             notes=self.notes.text(), plan=self._plan())
        except Exception as exc:  # noqa: BLE001
            return show_error(self, exc)
        if not data.customer_id:
            return show_error(self, "Please choose a customer.")
        self.complete.setEnabled(False)
        sale_id = run_action(self, self.ctx.sales.create_sale, data)
        if not sale_id:
            self._recalc()
            return
        sale = self.ctx.sales.get_sale(sale_id)
        pdf = run_action(self, self.ctx.delivery_notes.generate_for_sale, sale_id)
        box = QMessageBox(self)
        box.setWindowTitle("Sale completed")
        box.setIcon(QMessageBox.Icon.Information)
        box.setText(f"<b>{sale.sales_ref}</b> saved: {sale.customer_name}, {sale.product_names} × {sale.quantity}, "
                    f"{format_money(sale.total_minor)}.<br>Delivery note <b>{sale.delivery_note_number}</b> "
                    + ("created." if pdf else "could not be generated; open Delivery Notes to retry."))
        open_btn = box.addButton("Open delivery note", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("New sale", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        self.qty.setValue(1)
        self.discount.clear()
        self.pay_ref.clear()
        self.notes.clear()
        self.refresh()
        if box.clickedButton() is open_btn and self.main:
            self.main.go("Delivery Notes", select=sale.delivery_note_id)
