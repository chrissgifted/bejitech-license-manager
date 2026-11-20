from __future__ import annotations

from PySide6.QtWidgets import (
    QButtonGroup, QComboBox, QHBoxLayout, QInputDialog, QLabel, QPushButton, QSplitter, QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt

from bejitech.core.enums import StockState
from bejitech.core.money import format_money
from bejitech.core.timeutil import display_date, display_datetime
from bejitech.ui.dialogs.license_form import LicenseForm
from bejitech.ui.dialogs.reveal_key import copy_key, reveal_key
from bejitech.ui.views.base import Page
from bejitech.ui.widgets.common import (
    Card, DataTable, PageHeader, SearchBox, confirm, page_layout, run_action, show_error,
)

FILTERS = [("All", None)] + [(s.label, s.value) for s in StockState]


class InventoryPage(Page):
    title = "License Inventory"

    def __init__(self, ctx, main=None):
        super().__init__(ctx, main)
        lay = page_layout(self)
        h = PageHeader("License Inventory", "Purchased keys and their activation balances. Keys are encrypted and masked.")
        h.add_button("+ Add licence keys", self._add, primary=True)
        lay.addWidget(h)

        bar = QHBoxLayout()
        self.search = SearchBox("Search ref, product, supplier, last 5 characters…")
        self.search.search.connect(lambda _: self.refresh())
        bar.addWidget(self.search)
        self.product = QComboBox()
        self.product.currentIndexChanged.connect(lambda _: self.refresh())
        bar.addWidget(self.product)
        self.group = QButtonGroup(self)
        for i, (label, _v) in enumerate(FILTERS):
            b = QPushButton(label)
            b.setCheckable(True)
            b.setChecked(i == 0)
            self.group.addButton(b, i)
            bar.addWidget(b)
        self.group.idClicked.connect(lambda _: self.refresh())
        bar.addStretch(1)
        lay.addLayout(bar)

        split = QSplitter(Qt.Orientation.Vertical)
        self.table = DataTable(["Ref", "Product", "Key", "Supplier", "Capacity", "Allocated", "Confirmed",
                                "Remaining", "Expires", "State"], stretch_col=1)
        self.table.selection_changed_id.connect(self._show_detail)
        self.table.activated_id.connect(lambda i: self._edit())
        split.addWidget(self.table)

        detail = Card()
        self.detail_title = QLabel("Select a licence to see details and history")
        self.detail_title.setObjectName("CardTitle")
        detail.body.addWidget(self.detail_title)
        self.detail_info = QLabel("")
        self.detail_info.setWordWrap(True)
        self.detail_info.setObjectName("Muted")
        detail.body.addWidget(self.detail_info)
        self.history = DataTable(["When", "Event", "Change", "Allocated", "Customer", "Sale", "Note"], stretch_col=6)
        detail.body.addWidget(self.history)
        btns = QHBoxLayout()
        self.btn = {}
        for name, slot in (("👁 Reveal", self._reveal), ("Copy key", self._copy), ("Edit", self._edit),
                           ("Adjust capacity…", self._capacity), ("Disable / enable", self._toggle)):
            b = QPushButton(name)
            b.clicked.connect(slot)
            b.setEnabled(False)
            self.btn[name] = b
            btns.addWidget(b)
        btns.addStretch(1)
        detail.body.addLayout(btns)
        split.addWidget(detail)
        split.setSizes([420, 300])
        lay.addWidget(split, 1)

    def _fill_products(self):
        cur = self.product.currentData()
        self.product.blockSignals(True)
        self.product.clear()
        self.product.addItem("All products", None)
        for p in self.ctx.catalogue.list_products(include_archived=True):
            self.product.addItem(p.display_name, p.id)
        self.product.setCurrentIndex(max(0, self.product.findData(cur)))
        self.product.blockSignals(False)

    def refresh(self):
        self._fill_products()
        state = FILTERS[self.group.checkedId()][1] if self.group.checkedId() >= 0 else None
        rows = self.ctx.inventory.list_licenses(self.search.text(), state, self.product.currentData())
        self.table.set_rows([(r.id, [r.inventory_ref, r.product_name, f"•••• {r.key_suffix}", r.supplier or "",
                                     r.permitted_capacity, r.allocated_qty, r.confirmed_qty, r.remaining_qty,
                                     display_date(r.expiration_date) if r.expiration_date else "—",
                                     StockState(r.stock_state).label]) for r in rows],
                            right_align=(4, 5, 6, 7), state_col=9)
        self._show_detail(self.table.selected_id())

    def _show_detail(self, lid):
        for b in self.btn.values():
            b.setEnabled(lid is not None)
        if lid is None:
            self.detail_title.setText("Select a licence to see details and history")
            self.detail_info.setText("")
            self.history.set_rows([])
            return
        r = self.ctx.inventory.get_license(lid)
        self.detail_title.setText(f"{r.inventory_ref} · {r.product_name} · {r.masked_key}")
        cost = format_money(r.purchase_cost_minor, r.purchase_currency)
        if r.purchase_currency != "TZS":
            cost += f" @ {r.exchange_rate_to_tzs} = {format_money(r.purchase_cost_tzs)}"
        bits = [f"Supplier: {r.supplier or '—'}", f"Bought {display_date(r.purchase_date)} for {cost}",
                f"Multi-customer: {'Yes' if r.allows_multiple_customers else 'No'}",
                f"Reassignable: {'Yes' if r.reassignable else 'No'}",
                f"Expires: {display_date(r.expiration_date) if r.expiration_date else '—'}"]
        if r.restrictions:
            bits.append(f"Restrictions: {r.restrictions}")
        if r.disabled_reason:
            bits.append(f"Disabled: {r.disabled_reason}")
        if r.notes:
            bits.append(f"Notes: {r.notes}")
        self.detail_info.setText(" · ".join(bits))
        self.history.set_rows([(i, [display_datetime(h.created_at), h.event_type.title(),
                                    f"{h.qty_delta:+d}" if h.qty_delta else "",
                                    f"{h.allocated_before} → {h.allocated_after}", h.customer or "",
                                    h.sales_ref or "", h.note or ""])
                               for i, h in enumerate(self.ctx.inventory.history(lid))], state_col=1)
        self.btn["Disable / enable"].setText("Enable" if r.status == "DISABLED" else "Disable…")

    def _add(self):
        if LicenseForm(self.ctx, product_id=self.product.currentData(), parent=self).exec():
            self.refresh()

    def _sel(self):
        return self.table.selected_id()

    def _reveal(self):
        if lid := self._sel():
            reveal_key(self, self.ctx, lid, self.ctx.inventory.get_license(lid).inventory_ref)

    def _copy(self):
        if lid := self._sel():
            copy_key(self, self.ctx, lid)

    def _edit(self):
        if (lid := self._sel()) and LicenseForm(self.ctx, license_id=lid, parent=self).exec():
            self.refresh()

    def _capacity(self):
        lid = self._sel()
        if not lid:
            return
        r = self.ctx.inventory.get_license(lid)
        new, ok = QInputDialog.getInt(self, "Adjust capacity",
                                      f"Permitted activations for {r.inventory_ref} (currently {r.permitted_capacity}, "
                                      f"{r.allocated_qty} allocated):", r.permitted_capacity, 1, 100000)
        if not ok or new == r.permitted_capacity:
            return
        reason, ok = QInputDialog.getText(self, "Adjust capacity", "Reason (kept in the history):")
        if ok:
            run_action(self, self.ctx.inventory.adjust_capacity, lid, new, reason)
            self.refresh()

    def _toggle(self):
        lid = self._sel()
        if not lid:
            return
        r = self.ctx.inventory.get_license(lid)
        if r.status == "DISABLED":
            if confirm(self, "Enable licence", f"Enable {r.inventory_ref} for new sales again?"):
                run_action(self, self.ctx.inventory.set_disabled, lid, False)
        else:
            reason, ok = QInputDialog.getText(self, "Disable licence",
                                              f"Disable {r.inventory_ref}? It will not be offered for new sales.\n\nReason:")
            if ok:
                if not reason.strip():
                    return show_error(self, "A reason is required.")
                run_action(self, self.ctx.inventory.set_disabled, lid, True, reason)
        self.refresh()
