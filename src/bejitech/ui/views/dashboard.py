from __future__ import annotations

from datetime import date

from PySide6.QtWidgets import QComboBox, QGridLayout, QHBoxLayout, QLabel, QListWidget

from bejitech.core.money import format_money
from bejitech.core.timeutil import display_date
from bejitech.ui.theme import AMBER, GREEN, RED
from bejitech.ui.views.base import Page
from bejitech.ui.widgets.common import Card, DataTable, PageHeader, StatCard, page_layout

PERIODS = ["All time", "This month", "Last 30 days", "This year"]


def period_range(name: str) -> tuple[str | None, str | None]:
    t = date.today()
    if name == "This month":
        return t.replace(day=1).isoformat(), t.isoformat()
    if name == "Last 30 days":
        return date.fromordinal(t.toordinal() - 29).isoformat(), t.isoformat()
    if name == "This year":
        return t.replace(month=1, day=1).isoformat(), t.isoformat()
    return None, None


class DashboardPage(Page):
    title = "Dashboard"

    def __init__(self, ctx, main=None):
        super().__init__(ctx, main)
        lay = page_layout(self)
        self.header = PageHeader("Dashboard", display_date(date.today().isoformat()))
        self.period = QComboBox()
        self.period.addItems(PERIODS)
        self.period.currentTextChanged.connect(lambda _: self.refresh())
        self.header.actions.addWidget(QLabel("Sales period:"))
        self.header.actions.addWidget(self.period)
        self.header.add_button("+ New sale", lambda: main and main.go("New Sale"), primary=True)
        lay.addWidget(self.header)

        grid = QGridLayout()
        grid.setSpacing(12)
        labels = [
            ("total_products", "Products"), ("total_keys", "Purchased keys"),
            ("available_activations", "Available activations"), ("allocated_activations", "Allocated activations"),
            ("fully_allocated_keys", "Fully allocated keys"), ("total_customers", "Customers"),
            ("total_sales", "Sales"), ("revenue", "Revenue"), ("purchase_costs", "Purchase costs"),
            ("gross_profit", "Gross profit"),
        ]
        self.cards = {}
        for i, (key, label) in enumerate(labels):
            c = StatCard(label)
            self.cards[key] = c
            grid.addWidget(c, i // 5, i % 5)
        lay.addLayout(grid)

        row = QHBoxLayout()
        low = Card("Low-stock alerts")
        self.low_list = QListWidget()
        self.low_list.setObjectName("Plain")
        low.body.addWidget(self.low_list)
        row.addWidget(low, 1)
        recent = Card("Recent sales")
        self.recent = DataTable(["Ref", "Date", "Customer", "Product", "Qty", "Total", "Status"], stretch_col=3)
        recent.body.addWidget(self.recent)
        row.addWidget(recent, 2)
        lay.addLayout(row, 1)
        self.note = QLabel("Gross profit = revenue − cost of the activations sold. Purchase costs = money spent on "
                           "keys bought in the period.")
        self.note.setObjectName("Muted")
        lay.addWidget(self.note)

    def refresh(self):
        f, t = period_range(self.period.currentText())
        d = self.ctx.reports.dashboard(f, t)
        for key, card in self.cards.items():
            v = d[key]
            if key in ("revenue", "purchase_costs", "gross_profit"):
                card.set(format_money(v), (GREEN if v >= 0 else RED) if key == "gross_profit" else None)
            else:
                card.set(f"{v:,}")
        self.low_list.clear()
        for a in d["low_stock"]:
            self.low_list.addItem(f"⚠  {a['display_name']}: {a['available_activations']} available "
                                  f"(alert below {a['low_stock_threshold']})")
        if not d["low_stock"]:
            self.low_list.addItem("✓  All products are above their low-stock level.")
        self.cards["available_activations"].set(f"{d['available_activations']:,}",
                                                AMBER if d["low_stock"] else None)
        sales = self.ctx.sales.list_sales()[:12]
        self.recent.set_rows([(s.id, [s.sales_ref, display_date(s.sale_date), s.customer_name, s.product_names,
                                      s.quantity, format_money(s.total_minor, with_code=False), s.status.title()])
                              for s in sales], right_align=(4, 5), state_col=6)
