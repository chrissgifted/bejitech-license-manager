from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QPlainTextEdit, QVBoxLayout

from bejitech.core.dto import CustomerInput
from bejitech.ui.widgets.common import run_action


class CustomerForm(QDialog):
    def __init__(self, ctx, customer_id: int | None = None, parent=None):
        super().__init__(parent)
        self.ctx, self.customer_id, self.saved_id = ctx, customer_id, None
        self.setWindowTitle("Edit customer" if customer_id else "New customer")
        self.setMinimumWidth(440)
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.name, self.org, self.phone, self.email = QLineEdit(), QLineEdit(), QLineEdit(), QLineEdit()
        self.address, self.notes = QPlainTextEdit(), QPlainTextEdit()
        self.address.setFixedHeight(60)
        self.notes.setFixedHeight(60)
        self.phone.setPlaceholderText("+255 7xx xxx xxx")
        form.addRow("Full name *", self.name)
        form.addRow("Organisation", self.org)
        form.addRow("Phone", self.phone)
        form.addRow("Email", self.email)
        form.addRow("Address", self.address)
        form.addRow("Notes", self.notes)
        lay.addLayout(form)
        if customer_id:
            c = ctx.customers.get(customer_id)
            self.name.setText(c.full_name)
            self.org.setText(c.organization or "")
            self.phone.setText(c.phone or "")
            self.email.setText(c.email or "")
            self.address.setPlainText(c.address or "")
            self.notes.setPlainText(c.notes or "")
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Save).setObjectName("Primary")
        bb.accepted.connect(self._save)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _save(self):
        data = CustomerInput(full_name=self.name.text(), organization=self.org.text(), phone=self.phone.text(),
                             email=self.email.text(), address=self.address.toPlainText(),
                             notes=self.notes.toPlainText(), id=self.customer_id)
        cid = run_action(self, self.ctx.customers.save, data)
        if cid:
            self.saved_id = cid
            self.accept()
