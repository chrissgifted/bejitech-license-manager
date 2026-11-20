from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QComboBox, QHBoxLayout

from bejitech.core.money import format_money
from bejitech.ui.dialogs.product_form import ProductForm
from bejitech.ui.views.base import Page
from bejitech.ui.widgets.common import DataTable, PageHeader, SearchBox, confirm, page_layout, run_action


class ProductsPage(Page):
    title = "Software Products"

    def __init__(self, ctx, main=None):
        super().__init__(ctx, main)
        lay = page_layout(self)
        h = PageHeader("Software Products", "Your catalogue: Publisher → Product → Version → Edition → Licence type")
        h.add_button("Archive / restore", self._archive)
        h.add_button("Edit", self._edit)
        h.add_button("+ Add product", self._add, primary=True)
        lay.addWidget(h)
        bar = QHBoxLayout()
        self.search = SearchBox("Search products, publisher, version…")
        self.search.search.connect(lambda _: self.refresh())
        self.publisher = QComboBox()
        self.category = QComboBox()
        for c in (self.publisher, self.category):
            c.currentIndexChanged.connect(lambda _: self.refresh())
        self.archived = QCheckBox("Show archived")
        self.archived.toggled.connect(lambda _: self.refresh())
        bar.addWidget(self.search)
        bar.addWidget(self.publisher)
        bar.addWidget(self.category)
        bar.addWidget(self.archived)
        bar.addStretch(1)
        lay.addLayout(bar)
        self.table = DataTable(["Product", "Publisher", "Category", "Platform", "Licence type", "Price (TZS)",
                                "Keys", "Available", "Download link", "Status"], stretch_col=0)
        self.table.activated_id.connect(self._edit_id)
        lay.addWidget(self.table, 1)
        self._loading_filters = False

    def _fill_filters(self):
        self._loading_filters = True
        for combo, items, label in ((self.publisher, self.ctx.catalogue.list_publishers(), "All publishers"),
                                    (self.category, self.ctx.catalogue.list_categories(), "All categories")):
            cur = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(label, None)
            for it in items:
                combo.addItem(it, it)
            combo.setCurrentIndex(max(0, combo.findData(cur)))
            combo.blockSignals(False)
        self._loading_filters = False

    def refresh(self):
        if not self._loading_filters:
            self._fill_filters()
        rows = self.ctx.catalogue.list_products(self.search.text(), self.archived.isChecked(),
                                                self.publisher.currentData(), self.category.currentData())
        out = []
        for p in rows:
            status = "Archived" if p.is_archived else ("Low stock" if p.is_low_stock else "Active")
            link = ("✓ verified" if p.download_url_verified else "⚠ not verified") if p.download_url else "— none"
            out.append((p.id, [p.display_name, p.publisher, p.category, p.platform, p.license_type,
                               format_money(p.selling_price_minor, with_code=False), p.total_keys,
                               p.available_activations, link, status]))
        self.table.set_rows(out, right_align=(5, 6, 7), state_col=9)

    def _add(self):
        d = ProductForm(self.ctx, parent=self)
        if d.exec():
            self.refresh()
            self.table.select_id(d.saved_id)

    def _edit_id(self, pid):
        if ProductForm(self.ctx, pid, parent=self).exec():
            self.refresh()

    def _edit(self):
        pid = self.table.selected_id()
        if pid:
            self._edit_id(pid)

    def _archive(self):
        pid = self.table.selected_id()
        if not pid:
            return
        p = self.ctx.catalogue.get_product(pid)
        verb = "Restore" if p.is_archived else "Archive"
        if confirm(self, f"{verb} product", f"{verb} “{p.display_name}”?\n\nArchived products are hidden from "
                   "new sales but kept for history.", destructive=not p.is_archived):
            run_action(self, self.ctx.catalogue.set_archived, pid, not p.is_archived)
            self.refresh()
