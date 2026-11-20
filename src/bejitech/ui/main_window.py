from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QSettings, Qt, QTimer
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QListWidget, QMainWindow, QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

from bejitech import APP_NAME, __version__
from bejitech.core.timeutil import display_datetime
from bejitech.ui.dialogs.auth_dialogs import LoginDialog
from bejitech.ui.views.backup_restore import BackupPage
from bejitech.ui.views.customers import CustomersPage
from bejitech.ui.views.dashboard import DashboardPage
from bejitech.ui.views.delivery_notes import DeliveryNotesPage
from bejitech.ui.views.inventory import InventoryPage
from bejitech.ui.views.new_sale import NewSalePage
from bejitech.ui.views.products import ProductsPage
from bejitech.ui.views.reports import ReportsPage
from bejitech.ui.views.sales_history import SalesHistoryPage
from bejitech.ui.views.settings import SettingsPage
from bejitech.ui.widgets.common import show_error

PAGES = [
    ("Dashboard", "▦", DashboardPage), ("Software Products", "▤", ProductsPage),
    ("License Inventory", "⚿", InventoryPage), ("New Sale", "＋", NewSalePage), ("Customers", "☺", CustomersPage),
    ("Sales History", "≡", SalesHistoryPage), ("Delivery Notes", "✉", DeliveryNotesPage),
    ("Reports", "▥", ReportsPage), ("Backup & Restore", "⟲", BackupPage), ("Settings", "⚙", SettingsPage),
]


class _ActivityFilter(QObject):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.KeyPress, QEvent.Type.Wheel):
            self.callback()
        return False


class MainWindow(QMainWindow):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(1200, 760)
        root = QWidget()
        h = QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        side = QWidget()
        side.setObjectName("Sidebar")
        side.setFixedWidth(230)
        sv = QVBoxLayout(side)
        sv.setContentsMargins(0, 18, 0, 14)
        t = QLabel("  ◆ BEJITECH")
        t.setObjectName("SidebarTitle")
        s = QLabel("     License Manager")
        s.setObjectName("SidebarSub")
        sv.addWidget(t)
        sv.addWidget(s)
        sv.addSpacing(14)
        self.nav = QListWidget()
        for name, icon, _ in PAGES:
            self.nav.addItem(f"{icon}   {name}")
        sv.addWidget(self.nav, 1)
        self.backup_label = QLabel()
        self.backup_label.setObjectName("SidebarSub")
        self.backup_label.setWordWrap(True)
        self.backup_label.setContentsMargins(14, 0, 14, 4)
        sv.addWidget(self.backup_label)
        self.user_label = QLabel()
        self.user_label.setObjectName("SidebarSub")
        self.user_label.setContentsMargins(14, 0, 14, 4)
        sv.addWidget(self.user_label)
        lock = QPushButton("🔒  Lock")
        lock.clicked.connect(self.lock)
        lw = QWidget()
        ll = QHBoxLayout(lw)
        ll.setContentsMargins(12, 0, 12, 0)
        ll.addWidget(lock)
        sv.addWidget(lw)
        h.addWidget(side)

        self.stack = QStackedWidget()
        self.pages = {}
        for name, _, cls in PAGES:
            page = cls(ctx, self)
            self.pages[name] = page
            self.stack.addWidget(page)
        h.addWidget(self.stack, 1)
        self.setCentralWidget(root)
        self.statusBar().showMessage(f"{APP_NAME} {__version__} · Data: {ctx.paths.root}")
        self.nav.currentRowChanged.connect(self._show)

        self.idle = QTimer(self, singleShot=True)
        self.idle.timeout.connect(self.lock)
        self._filter = _ActivityFilter(lambda: self.idle.start())
        QApplication.instance().installEventFilter(self._filter)
        self.apply_security_settings()
        self._restore_geometry()
        self.nav.setCurrentRow(0)

    def apply_security_settings(self):
        self.idle.setInterval(self.ctx.settings.get_int("security.autolock_minutes", 15) * 60 * 1000)
        self.idle.start()

    def _show(self, row: int, select=None):
        if row < 0:
            return
        name = PAGES[row][0]
        page = self.pages[name]
        self.stack.setCurrentWidget(page)
        try:
            page.refresh(select=select) if select is not None else page.refresh()
        except Exception as exc:  # noqa: BLE001
            show_error(self, exc)
        self._update_side()

    def go(self, name: str, select=None):
        row = [p[0] for p in PAGES].index(name)
        self.nav.blockSignals(True)
        self.nav.setCurrentRow(row)
        self.nav.blockSignals(False)
        self._show(row, select)

    def _update_side(self):
        hist = self.ctx.backup.history()
        last = next((b for b in hist if b["verified"]), None)
        self.backup_label.setText(f"Last backup: {display_datetime(last['created_at'])} ✓" if last
                                  else "⚠ No backup yet")
        self.user_label.setText(f"Signed in as {self.ctx.auth.display_name or ''}")

    def lock(self):
        if not self.isVisible():
            return
        self.ctx.auth.lock()
        self.idle.stop()
        self.stack.setVisible(False)
        dlg = LoginDialog(self.ctx, self, locked=True)
        if dlg.exec():
            self.stack.setVisible(True)
            self.idle.start()
            self._show(self.nav.currentRow())
        else:
            QApplication.instance().quit()

    def _restore_geometry(self):
        st = QSettings("Bejitech", "LicenseManager")
        geo = st.value("geometry")
        if geo:
            self.restoreGeometry(geo)
        else:
            self.resize(1360, 860)

    def closeEvent(self, event):
        QSettings("Bejitech", "LicenseManager").setValue("geometry", self.saveGeometry())
        self.ctx.auth.lock()
        super().closeEvent(event)
