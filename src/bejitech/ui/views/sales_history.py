from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QSplitter

from bejitech.core.enums import PaymentMethod
from bejitech.core.money import format_money
from bejitech.core.timeutil import display_date, display_datetime
from bejitech.exports.csv_export import write_csv
from bejitech.ui.dialogs.cancel_sale import CancelSaleDialog
from bejitech.ui.views.base import Page
from bejitech.ui.widgets.common import (
    Card, DataTable, DateEdit, PageHeader, SearchBox, confirm, info, page_layout, run_action,
)


class SalesHistoryPage(Page):
    title = "Sales History"

    def __init__(self, ctx, main=None):
        super().__init__(ctx, main)
        lay = page_layout(self)
        h = PageHeader("Sales History", "Every sale, its licence allocations and delivery note")
        h.add_button("Export CSV", self._export)
        lay.addWidget(h)
        bar = QHBoxLayout()
        self.search = SearchBox("Search ref, customer, product, payment ref…")
        self.search.search.connect(lambda _: self.refresh())
        self.date_from = DateEdit(date.today().replace(month=1, day=1).isoformat())
        self.date_to = DateEdit()
        self.status = QComboBox()
        self.status.addItem("All statuses", None)
        self.status.addItem("Completed", "COMPLETED")
        self.status.addItem("Cancelled", "CANCELLED")
        self.payment = QComboBox()
        self.payment.addItem("All payments", None)
        for m in PaymentMethod:
            self.payment.addItem(m.label, m.value)
        for w in (self.date_from, self.date_to):
            w.dateChanged.connect(lambda _: self.refresh())
        for w in (self.status, self.payment):
            w.currentIndexChanged.connect(lambda _: self.refresh())
        bar.addWidget(self.search)
        bar.addWidget(QLabel("From"))
        bar.addWidget(self.date_from)
        bar.addWidget(QLabel("to"))
        bar.addWidget(self.date_to)
        bar.addWidget(self.status)
        bar.addWidget(self.payment)
        bar.addStretch(1)
        lay.addLayout(bar)
        split = QSplitter(Qt.Orientation.Vertical)
        self.table = DataTable(["Ref", "Date", "Customer", "Product", "Qty", "Total (TZS)", "Payment", "Status"],
                               stretch_col=3)
        self.table.selection_changed_id.connect(self._detail)
        split.addWidget(self.table)
        card = Card()
        self.d_title = QLabel("Select a sale")
        self.d_title.setObjectName("CardTitle")
        self.d_info = QLabel("")
        self.d_info.setObjectName("Muted")
        self.d_info.setWordWrap(True)
        card.body.addWidget(self.d_title)
        card.body.addWidget(self.d_info)
        self.allocs = DataTable(["Key ref", "Key", "Activations", "Status", "Confirmed"], stretch_col=1)
        card.body.addWidget(self.allocs)
        row = QHBoxLayout()
        self.b_confirm = QPushButton("Mark activation confirmed")
        self.b_confirm.clicked.connect(self._confirm)
        self.b_note = QPushButton("Open delivery note")
        self.b_note.clicked.connect(self._open_note)
        self.b_cancel = QPushButton("Cancel sale…")
        self.b_cancel.setObjectName("Danger")
        self.b_cancel.clicked.connect(self._cancel)
        for b in (self.b_confirm, self.b_note, self.b_cancel):
            row.addWidget(b)
        row.addStretch(1)
        card.body.addLayout(row)
        split.addWidget(card)
        split.setSizes([400, 280])
        lay.addWidget(split, 1)
        self._detail(None)

    def _sales(self):
        return self.ctx.sales.list_sales(self.search.text(), self.date_from.iso(), self.date_to.iso(),
                                         self.status.currentData(), payment_method=self.payment.currentData())

    def refresh(self, select: int | None = None):
        if select:
            self.date_from.blockSignals(True)
            self.date_from.set_iso("2000-01-01")
            self.date_from.blockSignals(False)
        self.table.set_rows([(s.id, [s.sales_ref, display_date(s.sale_date), s.customer_name, s.product_names,
                                     s.quantity, format_money(s.total_minor, with_code=False),
                                     PaymentMethod(s.payment_method).label, s.status.title()])
                             for s in self._sales()], right_align=(4, 5), state_col=7,
                            sort_keys={1: lambda v: v[0]})
        if select:
            self.table.select_id(select)
        self._detail(self.table.selected_id())

    def _detail(self, sid):
        for b in (self.b_confirm, self.b_note, self.b_cancel):
            b.setEnabled(sid is not None)
        if not sid:
            self.d_title.setText("Select a sale")
            self.d_info.setText("")
            self.allocs.set_rows([])
            return
        s = self.ctx.sales.get_sale(sid)
        self.d_title.setText(f"{s.sales_ref} · {s.customer_name} · {format_money(s.total_minor)}")
        bits = [f"{s.product_names} × {s.quantity}",
                f"Subtotal {format_money(s.subtotal_minor)}, discount {format_money(s.discount_minor)}",
                f"Paid by {PaymentMethod(s.payment_method).label}" + (f" ({s.payment_reference})" if s.payment_reference else ""),
                f"Delivery note {s.delivery_note_number or '—'}"]
        if s.cancel_reason:
            bits.append(f"Cancelled: {s.cancel_reason}")
        if s.notes:
            bits.append(f"Notes: {s.notes}")
        self.d_info.setText(" · ".join(bits))
        self.allocs.set_rows([(a.id, [a.inventory_ref, a.masked_key, a.quantity, a.status.title(),
                                      display_datetime(a.confirmed_at) if a.confirmed_at else ""])
                              for a in s.allocations], right_align=(2,), state_col=3)
        self.b_cancel.setEnabled(s.status == "COMPLETED")
        self.b_confirm.setEnabled(any(a.status == "ALLOCATED" for a in s.allocations) and s.status == "COMPLETED")

    def _confirm(self):
        sid = self.table.selected_id()
        if not sid:
            return
        s = self.ctx.sales.get_sale(sid)
        pending = [a for a in s.allocations if a.status == "ALLOCATED"]
        aid = self.allocs.selected_id() or (pending[0].id if len(pending) == 1 else None)
        if not aid:
            return info(self, "Select the key allocation to confirm.")
        if confirm(self, "Confirm activation", "Mark these activations as confirmed (the customer activated "
                   "successfully)? Confirmed activations are never returned to stock."):
            run_action(self, self.ctx.allocation.confirm, aid)
            self.refresh()

    def _open_note(self):
        sid = self.table.selected_id()
        if sid and self.main:
            self.main.go("Delivery Notes", select=self.ctx.sales.get_sale(sid).delivery_note_id)

    def _cancel(self):
        sid = self.table.selected_id()
        if sid and CancelSaleDialog(self.ctx, sid, self).exec():
            self.refresh()

    def _export(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(self, "Export sales", "sales.csv", "CSV (*.csv)")
        if path:
            rep = self.ctx.reports.sales_report(self.date_from.iso(), self.date_to.iso())
            if run_action(self, write_csv, path, rep):
                info(self, f"Exported {len(rep.rows)} sales.")
