"""Reusable widgets and helpers."""
from __future__ import annotations

import logging
import traceback
from collections.abc import Callable, Sequence

from PySide6.QtCore import QDate, QSortFilterProxyModel, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QDateEdit, QFrame, QHBoxLayout, QHeaderView, QInputDialog, QLabel,
    QLineEdit, QMessageBox, QPushButton, QTableView, QVBoxLayout, QWidget,
)

from bejitech.core.errors import BejitechError
from bejitech.core.money import format_money, to_minor
from bejitech.ui.theme import STATE_COLORS

log = logging.getLogger(__name__)


# ---------- messages ----------
def show_error(parent, exc: BaseException | str) -> None:
    if isinstance(exc, BejitechError) or isinstance(exc, str):
        QMessageBox.warning(parent, "Bejitech License Manager", str(exc))
    else:
        log.error("Unexpected error: %s", "".join(traceback.format_exception(exc)))
        QMessageBox.critical(parent, "Unexpected error",
                             f"Something went wrong:\n\n{exc}\n\nDetails were written to the log file.")


def info(parent, text: str, title: str = "Bejitech License Manager") -> None:
    QMessageBox.information(parent, title, text)


def confirm(parent, title: str, text: str, destructive: bool = False) -> bool:
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(text)
    box.setIcon(QMessageBox.Icon.Warning if destructive else QMessageBox.Icon.Question)
    yes = box.addButton("Yes, continue" if destructive else "Yes", QMessageBox.ButtonRole.AcceptRole)
    box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
    box.exec()
    return box.clickedButton() is yes


def typed_confirm(parent, title: str, text: str, word: str) -> bool:
    value, ok = QInputDialog.getText(parent, title, f"{text}\n\nType {word} to confirm:")
    return ok and value.strip().upper() == word


def run_action(parent, fn: Callable, *args, busy: bool = True, **kwargs):
    """Run a service call, show friendly errors, return the result (or None on error)."""
    if busy:
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    try:
        return fn(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001
        if busy:
            QApplication.restoreOverrideCursor()
            busy = False
        show_error(parent, exc)
        return None
    finally:
        if busy:
            QApplication.restoreOverrideCursor()


# ---------- layout pieces ----------
class Card(QFrame):
    def __init__(self, title: str | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(16, 14, 16, 14)
        self.body.setSpacing(8)
        if title:
            t = QLabel(title)
            t.setObjectName("CardTitle")
            self.body.addWidget(t)


class StatCard(Card):
    def __init__(self, label: str, parent=None):
        super().__init__(None, parent)
        self.value = QLabel("—")
        self.value.setObjectName("StatValue")
        lab = QLabel(label)
        lab.setObjectName("StatLabel")
        self.body.addWidget(lab)
        self.body.addWidget(self.value)
        self.setMinimumWidth(150)

    def set(self, text: str, color: str | None = None) -> None:
        self.value.setText(text)
        self.value.setStyleSheet(f"color: {color};" if color else "")


class PageHeader(QWidget):
    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        col = QVBoxLayout()
        t = QLabel(title)
        t.setObjectName("PageTitle")
        col.addWidget(t)
        self.subtitle = QLabel(subtitle)
        self.subtitle.setObjectName("PageSubtitle")
        if subtitle:
            col.addWidget(self.subtitle)
        lay.addLayout(col)
        lay.addStretch(1)
        self.actions = QHBoxLayout()
        lay.addLayout(self.actions)

    def add_button(self, text: str, slot, primary: bool = False) -> QPushButton:
        b = QPushButton(text)
        if primary:
            b.setObjectName("Primary")
        b.clicked.connect(slot)
        self.actions.addWidget(b)
        return b


def page_layout(widget: QWidget) -> QVBoxLayout:
    lay = QVBoxLayout(widget)
    lay.setContentsMargins(24, 20, 24, 20)
    lay.setSpacing(14)
    return lay


def primary_button(text: str, slot=None) -> QPushButton:
    b = QPushButton(text)
    b.setObjectName("Primary")
    if slot:
        b.clicked.connect(slot)
    return b


class SearchBox(QLineEdit):
    """Search field that emits `search` 250 ms after typing stops."""
    search = Signal(str)

    def __init__(self, placeholder: str = "Search…", parent=None):
        super().__init__(parent)
        self.setPlaceholderText("🔍  " + placeholder)
        self.setClearButtonEnabled(True)
        self.setMinimumWidth(280)
        self._t = QTimer(self, singleShot=True, interval=250)
        self._t.timeout.connect(lambda: self.search.emit(self.text().strip()))
        self.textChanged.connect(lambda _: self._t.start())


# ---------- table ----------
class _SortItem(QStandardItem):
    def __lt__(self, other):
        a, b = self.data(Qt.ItemDataRole.UserRole + 1), other.data(Qt.ItemDataRole.UserRole + 1)
        if a is not None and b is not None:
            return a < b
        return super().__lt__(other)


class DataTable(QTableView):
    """Sortable, read-only table. Each row carries an id; `activated_id` fires on double-click."""
    activated_id = Signal(int)
    selection_changed_id = Signal(object)

    def __init__(self, headers: Sequence[str], parent=None, stretch_col: int = 1):
        super().__init__(parent)
        self.model_ = QStandardItemModel(0, len(headers), self)
        self.model_.setHorizontalHeaderLabels(list(headers))
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model_)
        self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.proxy.setFilterKeyColumn(-1)
        self.setModel(self.proxy)
        self.setSortingEnabled(True)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(30)
        h = self.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        if 0 <= stretch_col < len(headers):
            h.setSectionResizeMode(stretch_col, QHeaderView.ResizeMode.Stretch)
        self.doubleClicked.connect(self._double)
        self.selectionModel().selectionChanged.connect(lambda *_: self.selection_changed_id.emit(self.selected_id()))

    def set_rows(self, rows: Sequence[tuple[int, Sequence]], right_align: Sequence[int] = (),
                 state_col: int | None = None, sort_keys: dict[int, Callable] | None = None) -> None:
        keep = self.selected_id()
        self.setSortingEnabled(False)
        self.model_.removeRows(0, self.model_.rowCount())
        for row_id, values in rows:
            items = []
            for c, v in enumerate(values):
                it = _SortItem("" if v is None else str(v))
                it.setData(row_id, Qt.ItemDataRole.UserRole)
                if sort_keys and c in sort_keys:
                    it.setData(sort_keys[c](values), Qt.ItemDataRole.UserRole + 1)
                elif isinstance(v, (int, float)):
                    it.setData(v, Qt.ItemDataRole.UserRole + 1)
                if c in right_align:
                    it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if state_col is not None and c == state_col:
                    color = STATE_COLORS.get(str(v).upper().replace(" ", "_"))
                    if color:
                        it.setForeground(QColor(color))
                        f = it.font()
                        f.setBold(True)
                        it.setFont(f)
                items.append(it)
            self.model_.appendRow(items)
        self.setSortingEnabled(True)
        if keep is not None:
            self.select_id(keep)

    def selected_id(self) -> int | None:
        idx = self.selectionModel().selectedRows()
        if not idx:
            return None
        return self.proxy.data(idx[0], Qt.ItemDataRole.UserRole)

    def select_id(self, row_id: int) -> None:
        for r in range(self.proxy.rowCount()):
            if self.proxy.data(self.proxy.index(r, 0), Qt.ItemDataRole.UserRole) == row_id:
                self.selectRow(r)
                return

    def _double(self, index):
        rid = self.proxy.data(index, Qt.ItemDataRole.UserRole)
        if rid is not None:
            self.activated_id.emit(rid)


# ---------- inputs ----------
class MoneyEdit(QLineEdit):
    """Amount entry: shows thousands separators, returns minor units."""
    value_changed = Signal()

    def __init__(self, currency: str = "TZS", parent=None):
        super().__init__(parent)
        self.currency = currency
        self.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.setPlaceholderText("0")
        self.textChanged.connect(lambda _: self.value_changed.emit())
        self.editingFinished.connect(self._reformat)

    def set_currency(self, currency: str) -> None:
        v = self.value_minor(silent=True)
        self.currency = currency
        self.set_value(v)

    def value_minor(self, silent: bool = False) -> int:
        try:
            return to_minor(self.text() or "0", self.currency)
        except BejitechError:
            if silent:
                return 0
            raise

    def set_value(self, minor: int) -> None:
        self.setText(format_money(minor, self.currency, with_code=False))

    def _reformat(self):
        try:
            self.set_value(self.value_minor())
        except BejitechError:
            pass


class DateEdit(QDateEdit):
    def __init__(self, iso: str | None = None, parent=None, allow_empty: bool = False):
        super().__init__(parent)
        self.setCalendarPopup(True)
        self.setDisplayFormat("dd MMM yyyy")
        self.allow_empty = allow_empty
        if allow_empty:
            self.setMinimumDate(QDate(2000, 1, 1))
            self.setSpecialValueText("—")
        self.set_iso(iso)

    def set_iso(self, iso: str | None) -> None:
        if iso:
            self.setDate(QDate.fromString(iso[:10], "yyyy-MM-dd"))
        elif self.allow_empty:
            self.setDate(self.minimumDate())
        else:
            self.setDate(QDate.currentDate())

    def iso(self) -> str | None:
        if self.allow_empty and self.date() == self.minimumDate():
            return None
        return self.date().toString("yyyy-MM-dd")
