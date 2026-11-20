"""First-run setup, sign-in, key recovery and re-authentication dialogs."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QInputDialog, QLabel, QLineEdit, QVBoxLayout,
)

from bejitech import APP_NAME
from bejitech.core.errors import AuthError, KeyStoreError
from bejitech.ui.widgets.common import show_error


def _pw() -> QLineEdit:
    e = QLineEdit()
    e.setEchoMode(QLineEdit.EchoMode.Password)
    return e


def _title(text: str, sub: str) -> list[QLabel]:
    t = QLabel(text)
    t.setObjectName("PageTitle")
    s = QLabel(sub)
    s.setObjectName("Muted")
    s.setWordWrap(True)
    return [t, s]


class FirstRunDialog(QDialog):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.setWindowTitle(f"{APP_NAME}: first-time setup")
        self.setMinimumWidth(480)
        lay = QVBoxLayout(self)
        for w in _title("Welcome to Bejitech License Manager", "Create the administrator account."):
            lay.addWidget(w)
        form = QFormLayout()
        self.name = QLineEdit(ctx.settings.get("seller.name", ""))
        self.user = QLineEdit("admin")
        self.pw1, self.pw2 = _pw(), _pw()
        self.rec1, self.rec2 = _pw(), _pw()
        form.addRow("Administrator name", self.name)
        form.addRow("Username", self.user)
        form.addRow("Password (8+ characters)", self.pw1)
        form.addRow("Confirm password", self.pw2)
        form.addRow("Recovery passphrase (12+)", self.rec1)
        form.addRow("Confirm passphrase", self.rec2)
        lay.addLayout(form)
        warn = QLabel("⚠ Write the recovery passphrase down and keep it somewhere safe. It is the only way "
                      "to recover your licence keys if this Mac's Keychain is lost or you move to a new Mac "
                      "without a backup.")
        warn.setWordWrap(True)
        warn.setObjectName("Warning")
        lay.addWidget(warn)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText("Create account")
        bb.button(QDialogButtonBox.StandardButton.Ok).setObjectName("Primary")
        bb.accepted.connect(self._ok)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _ok(self):
        if self.pw1.text() != self.pw2.text():
            return show_error(self, "The passwords do not match.")
        if self.rec1.text() != self.rec2.text():
            return show_error(self, "The recovery passphrases do not match.")
        try:
            self.ctx.auth.create_admin(self.name.text(), self.user.text(), self.pw1.text(), self.rec1.text())
        except Exception as exc:  # noqa: BLE001
            return show_error(self, exc)
        self.accept()


class LoginDialog(QDialog):
    def __init__(self, ctx, parent=None, locked: bool = False):
        super().__init__(parent)
        self.ctx = ctx
        self.setWindowTitle(APP_NAME)
        self.setMinimumWidth(400)
        lay = QVBoxLayout(self)
        for w in _title("Bejitech License Manager",
                        "Locked after inactivity. Sign in to continue." if locked else "Sign in to continue."):
            lay.addWidget(w)
        form = QFormLayout()
        self.user = QLineEdit(ctx.auth.username or "admin")
        self.pw = _pw()
        form.addRow("Username", self.user)
        form.addRow("Password", self.pw)
        lay.addLayout(form)
        self.msg = QLabel("")
        self.msg.setObjectName("Danger")
        lay.addWidget(self.msg)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText("Sign in")
        bb.button(QDialogButtonBox.StandardButton.Ok).setObjectName("Primary")
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText("Quit")
        bb.accepted.connect(self._ok)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.pw.setFocus(Qt.FocusReason.OtherFocusReason)

    def _ok(self):
        try:
            self.ctx.auth.login(self.user.text(), self.pw.text())
        except AuthError as exc:
            self.msg.setText(str(exc))
            self.pw.selectAll()
            return
        except KeyStoreError as exc:
            if not recover_keys(self, self.ctx, str(exc)):
                return
        except Exception as exc:  # noqa: BLE001
            return show_error(self, exc)
        self.accept()


def recover_keys(parent, ctx, reason: str) -> bool:
    while True:
        text, ok = QInputDialog.getText(parent, "Recover encryption key",
                                        f"{reason}\n\nRecovery passphrase:", QLineEdit.EchoMode.Password)
        if not ok:
            return False
        try:
            ctx.auth.recover_with_passphrase(text)
            return True
        except Exception as exc:  # noqa: BLE001
            show_error(parent, exc)


def ensure_recent_auth(parent, ctx) -> bool:
    """Ask for the password again if the last sign-in was more than 5 minutes ago."""
    if not ctx.auth.needs_reauth():
        return True
    text, ok = QInputDialog.getText(parent, "Confirm it's you",
                                    "Enter your password to view or copy licence keys:",
                                    QLineEdit.EchoMode.Password)
    if not ok:
        return False
    try:
        ctx.auth.reauthenticate(text)
        return True
    except AuthError as exc:
        show_error(parent, exc)
        return False
