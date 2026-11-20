from __future__ import annotations

import shutil

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QPushButton, QSplitter, QVBoxLayout, QWidget

from bejitech.core.timeutil import display_date
from bejitech.ui.views.base import Page
from bejitech.ui.widgets.common import DataTable, PageHeader, SearchBox, confirm, info, page_layout, run_action
from bejitech.ui.widgets.pdf_tools import PdfPreview, open_url, print_pdf, reveal_in_finder


class DeliveryNotesPage(Page):
    title = "Delivery Notes"

    def __init__(self, ctx, main=None):
        super().__init__(ctx, main)
        lay = page_layout(self)
        lay.addWidget(PageHeader("Delivery Notes", "Product-branded A4 PDFs linked to each sale"))
        self.search = SearchBox("Search note number, sale ref, customer…")
        self.search.search.connect(lambda _: self.refresh())
        lay.addWidget(self.search)
        split = QSplitter(Qt.Orientation.Horizontal)
        self.table = DataTable(["Number", "Date", "Sale", "Customer", "Status"], stretch_col=3)
        self.table.selection_changed_id.connect(self._preview)
        split.addWidget(self.table)
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        btns = QHBoxLayout()
        self.buttons = []
        for text, slot in (("Save PDF…", self._save), ("Print…", self._print), ("Prepare email", self._email),
                           ("Show in Finder", self._reveal), ("Re-issue with current details", self._reissue)):
            b = QPushButton(text)
            b.clicked.connect(slot)
            btns.addWidget(b)
            self.buttons.append(b)
        btns.addStretch(1)
        rl.addLayout(btns)
        self.status = QLabel("")
        self.status.setObjectName("Muted")
        self.status.setWordWrap(True)
        rl.addWidget(self.status)
        self.viewer = PdfPreview()
        rl.addWidget(self.viewer, 1)
        split.addWidget(right)
        split.setSizes([420, 620])
        lay.addWidget(split, 1)
        self._current = None

    def refresh(self, select: int | None = None):
        notes = self.ctx.delivery_notes.list_notes(self.search.text())
        self.table.set_rows([(n.id, [n.note_number, display_date(n.delivery_date), n.sales_ref, n.customer_name,
                                     n.status.title()]) for n in notes], state_col=4)
        if select:
            self.table.select_id(select)
        elif self.table.selected_id() is None and notes:
            self.table.selectRow(0)
        self._preview(self.table.selected_id())

    def _preview(self, nid):
        for b in self.buttons:
            b.setEnabled(nid is not None)
        if not nid:
            self.viewer.load(None)
            self.status.setText("No delivery note selected.")
            self._current = None
            return
        path = run_action(self, self.ctx.delivery_notes.pdf_file, nid)
        self._current = (nid, path)
        self.viewer.load(path)
        note = next((n for n in self.ctx.delivery_notes.list_notes() if n.id == nid), None)
        self.status.setText(f"{note.note_number} · {note.status.title()} · {path}" if note and path else "")

    def _path(self):
        return self._current[1] if self._current else None

    def _save(self):
        p = self._path()
        if not p:
            return
        dest, _ = QFileDialog.getSaveFileName(self, "Save delivery note", p.name, "PDF (*.pdf)")
        if dest:
            shutil.copy2(p, dest)
            info(self, "Delivery note saved.")

    def _print(self):
        if p := self._path():
            run_action(self, print_pdf, self, p, busy=False)

    def _reveal(self):
        if p := self._path():
            reveal_in_finder(p)

    def _email(self):
        if not self._current:
            return
        d = run_action(self, self.ctx.delivery_notes.email_draft, self._current[0])
        if not d:
            return
        info(self, "Your email app will open with the subject and message filled in.\n\n"
                   "The PDF is NOT attached automatically: Finder will show the file so you can drag it "
                   "into the email." + ("" if d["to"] else "\n\nThis customer has no email address saved."))
        open_url(d["url"])
        reveal_in_finder(self._path())

    def _reissue(self):
        if not self._current:
            return
        if confirm(self, "Re-issue delivery note", "Create a new revision using today's seller and customer "
                   "details? The current note will be marked VOID."):
            new_id = run_action(self, self.ctx.delivery_notes.new_revision, self._current[0])
            if new_id:
                self.refresh(select=new_id)
