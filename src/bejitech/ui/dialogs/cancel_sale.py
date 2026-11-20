from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QVBoxLayout, QWidget,
)

from bejitech.ui.widgets.common import run_action, show_error, typed_confirm


class CancelSaleDialog(QDialog):
    def __init__(self, ctx, sale_id: int, parent=None):
        super().__init__(parent)
        self.ctx, self.sale_id = ctx, sale_id
        sale = ctx.sales.get_sale(sale_id)
        self.setWindowTitle(f"Cancel sale {sale.sales_ref}")
        self.setMinimumWidth(560)
        lay = QVBoxLayout(self)
        intro = QLabel(f"<b>{sale.sales_ref}</b> · {sale.customer_name} · {sale.product_names} × {sale.quantity}"
                       "<br>Activations are only returned to stock when it is allowed. Everything else is "
                       "recorded as consumed and stays used.")
        intro.setWordWrap(True)
        lay.addWidget(intro)
        f = QFormLayout()
        self.reason = QLineEdit()
        self.reason.setPlaceholderText("Required, e.g. customer refund, entered by mistake")
        f.addRow("Reason *", self.reason)
        self.not_delivered = QCheckBox("The licence key was never given to the customer")
        self.not_delivered.toggled.connect(self._refresh)
        f.addRow("", self.not_delivered)
        lay.addLayout(f)
        self.opts_box = QWidget()
        self.opts_lay = QVBoxLayout(self.opts_box)
        self.opts_lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.opts_box)
        self.checks: dict[int, QCheckBox] = {}
        self._refresh()
        bb = QDialogButtonBox()
        go = bb.addButton("Cancel sale", QDialogButtonBox.ButtonRole.AcceptRole)
        go.setObjectName("Primary")
        bb.addButton("Keep sale", QDialogButtonBox.ButtonRole.RejectRole)
        bb.accepted.connect(self._go)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _refresh(self, *_):
        while self.opts_lay.count():
            w = self.opts_lay.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.checks.clear()
        for o in self.ctx.sales.cancellation_options(self.sale_id, self.not_delivered.isChecked()):
            if o.can_release:
                cb = QCheckBox(f"Return {o.quantity} activation(s) to {o.inventory_ref} ({o.masked_key[-5:]}): {o.reason}")
                cb.setChecked(True)
                self.checks[o.allocation_id] = cb
                self.opts_lay.addWidget(cb)
            else:
                lab = QLabel(f"• {o.inventory_ref}: {o.quantity} activation(s) will be recorded as consumed. {o.reason}")
                lab.setWordWrap(True)
                lab.setObjectName("Muted")
                self.opts_lay.addWidget(lab)

    def _go(self):
        if not self.reason.text().strip():
            return show_error(self, "Please give a reason for cancelling.")
        if not typed_confirm(self, "Confirm cancellation", "This cannot be undone.", "CANCEL"):
            return
        release = {aid for aid, cb in self.checks.items() if cb.isChecked()}
        if run_action(self, self.ctx.sales.cancel_sale, self.sale_id, self.reason.text(), release,
                      self.not_delivered.isChecked()) is None and self.ctx.sales.get_sale(self.sale_id).status != "CANCELLED":
            return
        self.accept()
