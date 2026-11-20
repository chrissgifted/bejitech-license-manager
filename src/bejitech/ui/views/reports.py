from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QFileDialog, QHBoxLayout, QLabel, QTabBar

from bejitech.exports.csv_export import write_csv
from bejitech.pdf.report_pdf import write_report_pdf
from bejitech.ui.views.base import Page
from bejitech.ui.views.dashboard import PERIODS, period_range
from bejitech.ui.widgets.common import DataTable, PageHeader, info, page_layout, run_action
from bejitech.ui.widgets.pdf_tools import open_file

REPORTS = [("inventory", "Inventory"), ("sales", "Sales"), ("customers", "Customers"),
           ("activations", "Activation balances"), ("profit", "Profit")]


class ReportsPage(Page):
    title = "Reports"

    def __init__(self, ctx, main=None):
        super().__init__(ctx, main)
        lay = page_layout(self)
        h = PageHeader("Reports", "Export to PDF or CSV (opens in Numbers or Excel)")
        h.add_button("Export CSV…", self._csv)
        h.add_button("Export PDF…", self._pdf, primary=True)
        lay.addWidget(h)
        self.tabs = QTabBar()
        for _, label in REPORTS:
            self.tabs.addTab(label)
        self.tabs.currentChanged.connect(lambda _: self.refresh())
        bar = QHBoxLayout()
        bar.addWidget(self.tabs)
        bar.addStretch(1)
        self.period_lab = QLabel("Period:")
        self.period = QComboBox()
        self.period.addItems(PERIODS)
        self.period.setCurrentText("This month")
        self.period.currentTextChanged.connect(lambda _: self.refresh())
        bar.addWidget(self.period_lab)
        bar.addWidget(self.period)
        lay.addLayout(bar)
        self.subtitle = QLabel("")
        self.subtitle.setObjectName("Muted")
        lay.addWidget(self.subtitle)
        self.table = None
        self.lay = lay
        self.report = None

    def _current(self):
        name = REPORTS[self.tabs.currentIndex()][0]
        f, t = period_range(self.period.currentText())
        return self.ctx.reports.report(name, f, t), name

    def refresh(self):
        name = REPORTS[self.tabs.currentIndex()][0]
        dated = name in ("sales", "customers", "profit")
        self.period.setVisible(dated)
        self.period_lab.setVisible(dated)
        self.report, _ = self._current()
        if self.table:
            self.lay.removeWidget(self.table)
            self.table.deleteLater()
        self.table = DataTable(self.report.headers, stretch_col=1)
        rows = [(i, r) for i, r in enumerate(self.report.rows)]
        if self.report.totals:
            rows.append((len(rows), self.report.totals))
        self.table.set_rows(rows, right_align=tuple(range(2, len(self.report.headers))))
        self.table.setSortingEnabled(False)
        self.lay.addWidget(self.table, 1)
        self.subtitle.setText(f"{self.report.title} · {self.report.subtitle} · {len(self.report.rows)} row(s)")

    def _csv(self):
        if not self.report:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", f"{self.report.title}.csv", "CSV (*.csv)")
        if path and run_action(self, write_csv, path, self.report):
            info(self, "CSV exported.")

    def _pdf(self):
        if not self.report:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export PDF", f"{self.report.title}.pdf", "PDF (*.pdf)")
        if path and run_action(self, write_report_pdf, path, self.report, self.ctx.settings.get("seller.name")):
            open_file(path)
