"""PDF preview, printing and opening files with the operating system."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSizeF, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QPainter
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtPrintSupport import QPrintDialog, QPrinter


class PdfPreview(QPdfView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.doc = QPdfDocument(self)
        self.setDocument(self.doc)
        self.setPageMode(QPdfView.PageMode.MultiPage)
        self.setZoomMode(QPdfView.ZoomMode.FitToWidth)

    def load(self, path: Path | None) -> None:
        self.doc.close()
        if path:
            self.doc.load(str(path))


def print_pdf(parent, path: Path) -> bool:
    doc = QPdfDocument(parent)
    doc.load(str(path))
    if doc.status() != QPdfDocument.Status.Ready:
        return False
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    dlg = QPrintDialog(printer, parent)
    if dlg.exec() != QPrintDialog.DialogCode.Accepted:
        return False
    painter = QPainter(printer)
    try:
        for i in range(doc.pageCount()):
            if i:
                printer.newPage()
            rect = painter.viewport()
            page = doc.pagePointSize(i)
            scale = min(rect.width() / page.width(), rect.height() / page.height())
            size = QSizeF(page.width() * scale, page.height() * scale)
            img = doc.render(i, size.toSize())
            painter.drawImage(QRectF(QPointF(0, 0), size), img)
    finally:
        painter.end()
    return True


def open_file(path: Path) -> None:
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


def reveal_in_finder(path: Path) -> None:
    path = Path(path)
    if sys.platform == "darwin":
        subprocess.run(["open", "-R", str(path)], check=False)
    elif sys.platform.startswith("win"):
        subprocess.run(["explorer", "/select,", str(path)], check=False)
    else:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))


def open_url(url: str) -> None:
    QDesktopServices.openUrl(QUrl(url))
