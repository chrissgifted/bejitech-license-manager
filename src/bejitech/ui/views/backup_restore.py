from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFormLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QPushButton,
)

from bejitech.core.timeutil import display_datetime
from bejitech.services.backup_service import EXTENSION
from bejitech.ui.views.base import Page
from bejitech.ui.widgets.common import (
    Card, DataTable, PageHeader, info, page_layout, primary_button, run_action, show_error, typed_confirm,
)


def _pw() -> QLineEdit:
    e = QLineEdit()
    e.setEchoMode(QLineEdit.EchoMode.Password)
    return e


class BackupPage(Page):
    title = "Backup & Restore"

    def __init__(self, ctx, main=None):
        super().__init__(ctx, main)
        lay = page_layout(self)
        lay.addWidget(PageHeader("Backup & Restore", "Encrypted backups of your database, logos and delivery notes"))
        row = QHBoxLayout()
        c = Card("Create encrypted backup")
        f = QFormLayout()
        self.dest = QLineEdit(str(ctx.paths.backups))
        choose = QPushButton("Choose…")
        choose.clicked.connect(self._choose_dest)
        d = QHBoxLayout()
        d.addWidget(self.dest, 1)
        d.addWidget(choose)
        self.pw1, self.pw2 = _pw(), _pw()
        f.addRow("Save to", d)
        f.addRow("Backup password", self.pw1)
        f.addRow("Confirm password", self.pw2)
        c.body.addLayout(f)
        hint = QLabel("Tip: save a copy on an external disk or iCloud Drive. Without the backup password the "
                      "backup cannot be opened. It is checked automatically after it is written.")
        hint.setWordWrap(True)
        hint.setObjectName("Muted")
        c.body.addWidget(hint)
        c.body.addWidget(primary_button("Create encrypted backup", self._backup))
        row.addWidget(c, 1)

        r = Card("Verify or restore a backup")
        warn = QLabel("⚠ Restoring replaces ALL current data. A safety backup of the current data is created "
                      "first (protected with the same password you enter). The app closes afterwards and must "
                      "be reopened.")
        warn.setWordWrap(True)
        warn.setObjectName("Warning")
        r.body.addWidget(warn)
        vb = QPushButton("Verify a backup file…")
        vb.clicked.connect(self._verify)
        rb = QPushButton("Restore from backup…")
        rb.setObjectName("Danger")
        rb.clicked.connect(self._restore)
        r.body.addWidget(vb)
        r.body.addWidget(rb)
        r.body.addStretch(1)
        row.addWidget(r, 1)
        lay.addLayout(row)

        h = Card("Backup history")
        self.table = DataTable(["Created", "Type", "File", "Size", "Verified"], stretch_col=2)
        h.body.addWidget(self.table)
        cons = QPushButton("Check inventory consistency")
        cons.clicked.connect(self._consistency)
        h.body.addWidget(cons)
        lay.addWidget(h, 1)

    def refresh(self):
        self.table.set_rows([(i, [display_datetime(b["created_at"]), b["kind"].replace("_", " ").title(),
                                  b["file_path"], f"{b['size_bytes'] / 1024:,.0f} KB",
                                  "✓ Verified" if b["verified"] else "✕ Failed"])
                             for i, b in enumerate(self.ctx.backup.history())])

    def _choose_dest(self):
        d = QFileDialog.getExistingDirectory(self, "Backup folder", self.dest.text())
        if d:
            self.dest.setText(d)

    def _backup(self):
        if self.pw1.text() != self.pw2.text():
            return show_error(self, "The passwords do not match.")
        path = run_action(self, self.ctx.backup.create_backup, Path(self.dest.text()), self.pw1.text())
        if path:
            self.pw1.clear()
            self.pw2.clear()
            info(self, f"Backup created and verified:\n{path}")
        self.refresh()

    def _ask(self, title):
        path, _ = QFileDialog.getOpenFileName(self, title, str(self.ctx.paths.backups),
                                              f"Bejitech backup (*{EXTENSION})")
        if not path:
            return None, None
        pw, ok = QInputDialog.getText(self, title, "Backup password:", QLineEdit.EchoMode.Password)
        return (path, pw) if ok else (None, None)

    def _verify(self):
        path, pw = self._ask("Verify backup")
        if path:
            s = run_action(self, self.ctx.backup.verify_backup, path, pw)
            if s:
                c = s["counts"]
                info(self, f"Backup is valid.\n\nCreated: {display_datetime(s['created_at'])}\n"
                           f"App version: {s['app_version']} · schema {s['schema_version']}\n"
                           f"{c['products']} products, {c['licenses']} licence keys, {c['customers']} customers, "
                           f"{c['sales']} sales, {s['files']} files checked.")

    def _restore(self):
        path, pw = self._ask("Restore backup")
        if not path:
            return
        if not typed_confirm(self, "Restore backup", "All current data will be replaced by this backup.",
                             "RESTORE"):
            return
        safety = run_action(self, self.ctx.backup.restore_backup, path, pw)
        if safety:
            info(self, f"Restore complete. A safety copy of your previous data was saved as:\n{safety}\n\n"
                       "The app will now close. Please open it again and sign in.")
            QApplication.instance().quit()

    def _consistency(self):
        problems = run_action(self, self.ctx.inventory.verify_consistency)
        if problems is None:
            return
        if problems:
            show_error(self, "Inventory inconsistencies found:\n\n" + "\n".join(problems))
        else:
            info(self, "Inventory is consistent: every key's allocated and confirmed counts match its allocation history.")
