from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QSplitter

from bejitech.core.money import format_money
from bejitech.core.timeutil import display_date
from bejitech.ui.dialogs.customer_form import CustomerForm
from bejitech.ui.views.base import Page
from bejitech.ui.widgets.common import Card, DataTable, PageHeader, SearchBox, confirm, page_layout, run_action


class CustomersPage(Page):
    title = "Customers"

    def __init__(self, ctx, main=None):
        super().__init__(ctx, main)
        lay = page_layout(self)
        h = PageHeader("Customers", "Contact details and purchase history")
        h.add_button("Archive / restore", self._archive)
        h.add_button("Edit", self._edit)
        h.add_button("+ Add customer", self._add, primary=True)
        lay.addWidget(h)
        bar = QHBoxLayout()
        self.search = SearchBox("Search name, organisation, phone, email…")
        self.search.search.connect(lambda _: self.refresh())
        self.archived = QCheckBox("Show archived")
        self.archived.toggled.connect(lambda _: self.refresh())
        bar.addWidget(self.search)
        bar.addWidget(self.archived)
        bar.addStretch(1)
        lay.addLayout(bar)
        split = QSplitter(Qt.Orientation.Vertical)
        self.table = DataTable(["Ref", "Name", "Organisation", "Phone", "Email", "Purchases", "Total spent (TZS)"])
        self.table.activated_id.connect(lambda _: self._edit())
        self.table.selection_changed_id.connect(self._history)
        split.addWidget(self.table)
        card = Card()
        self.hist_title = QLabel("Purchase history")
        self.hist_title.setObjectName("CardTitle")
        card.body.addWidget(self.hist_title)
        self.hist = DataTable(["Sale", "Date", "Product", "Qty", "Keys", "Total", "Delivery note", "Status"], stretch_col=2)
        self.hist.activated_id.connect(lambda sid: self.main and self.main.go("Sales History", select=sid))
        card.body.addWidget(self.hist)
        split.addWidget(card)
        lay.addWidget(split, 1)

    def refresh(self):
        rows = self.ctx.customers.list(self.search.text(), self.archived.isChecked())
        self.table.set_rows([(c.id, [c.customer_ref, c.full_name + (" (archived)" if c.is_archived else ""),
                                     c.organization or "", c.phone or "", c.email or "", c.purchases,
                                     format_money(c.total_spent_minor, with_code=False)]) for c in rows],
                            right_align=(5, 6))
        self._history(self.table.selected_id())

    def _history(self, cid):
        if not cid:
            self.hist_title.setText("Purchase history (select a customer)")
            self.hist.set_rows([])
            return
        c = self.ctx.customers.get(cid)
        self.hist_title.setText(f"Purchase history: {c.full_name}")
        self.hist.set_rows([(s.id, [s.sales_ref, display_date(s.sale_date), s.product_names, s.quantity,
                                    ", ".join(a.masked_key[-5:] for a in s.allocations),
                                    format_money(s.total_minor, with_code=False), s.delivery_note_number or "",
                                    s.status.title()]) for s in self.ctx.customers.history(cid)],
                           right_align=(3, 5), state_col=7)

    def _add(self):
        d = CustomerForm(self.ctx, parent=self)
        if d.exec():
            self.refresh()
            self.table.select_id(d.saved_id)

    def _edit(self):
        cid = self.table.selected_id()
        if cid and CustomerForm(self.ctx, cid, parent=self).exec():
            self.refresh()

    def _archive(self):
        cid = self.table.selected_id()
        if not cid:
            return
        c = self.ctx.customers.get(cid)
        verb = "Restore" if c.is_archived else "Archive"
        if confirm(self, f"{verb} customer", f"{verb} {c.full_name}? Their history is kept.",
                   destructive=not c.is_archived):
            run_action(self, self.ctx.customers.set_archived, cid, not c.is_archived)
            self.refresh()
