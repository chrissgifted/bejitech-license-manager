from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from bejitech.ui.dialogs.auth_dialogs import ensure_recent_auth
from bejitech.ui.widgets.common import info, run_action

REVEAL_SECONDS = 30


def copy_key(parent, ctx, license_id: int) -> None:
    if not ensure_recent_auth(parent, ctx):
        return
    key = run_action(parent, ctx.inventory.reveal_key, license_id, "copy")
    if key is None:
        return
    _copy(ctx, key)
    secs = ctx.settings.get_int("security.clipboard_clear_seconds", 60)
    info(parent, f"Licence key copied. The clipboard will be cleared in {secs} seconds.")


def _copy(ctx, key: str) -> None:
    clip = QGuiApplication.clipboard()
    clip.setText(key)
    secs = ctx.settings.get_int("security.clipboard_clear_seconds", 60)

    def clear():
        if clip.text() == key:
            clip.clear()

    QTimer.singleShot(secs * 1000, QGuiApplication.instance(), clear)


class RevealKeyDialog(QDialog):
    """Shows a decrypted key for 30 seconds."""

    def __init__(self, ctx, license_id: int, key: str, ref: str, parent=None):
        super().__init__(parent)
        self.ctx, self.key = ctx, key
        self.setWindowTitle(f"Licence key {ref}")
        lay = QVBoxLayout(self)
        lab = QLabel(key)
        lab.setObjectName("KeyLabel")
        lab.setTextInteractionFlags(lab.textInteractionFlags())
        lay.addWidget(lab)
        self.count = QLabel()
        self.count.setObjectName("Muted")
        lay.addWidget(self.count)
        row = QHBoxLayout()
        cp = QPushButton("Copy")
        cp.clicked.connect(self._copy)
        close = QPushButton("Hide")
        close.clicked.connect(self.accept)
        row.addStretch(1)
        row.addWidget(cp)
        row.addWidget(close)
        lay.addLayout(row)
        self.remaining = REVEAL_SECONDS
        self.timer = QTimer(self, interval=1000)
        self.timer.timeout.connect(self._tick)
        self.timer.start()
        self._tick(first=True)
        self.license_id = license_id

    def _tick(self, first=False):
        if not first:
            self.remaining -= 1
        if self.remaining <= 0:
            self.accept()
        self.count.setText(f"This key will be hidden in {self.remaining} s.")

    def _copy(self):
        self.ctx.audit.log("KEY_COPIED", "license", None, license_id=self.license_id)
        _copy(self.ctx, self.key)
        self.count.setText("Copied. Clipboard will be cleared automatically.")


def reveal_key(parent, ctx, license_id: int, ref: str) -> None:
    if not ensure_recent_auth(parent, ctx):
        return
    key = run_action(parent, ctx.inventory.reveal_key, license_id)
    if key is not None:
        RevealKeyDialog(ctx, license_id, key, ref, parent).exec()
