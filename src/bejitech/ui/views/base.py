from PySide6.QtWidgets import QWidget


class Page(QWidget):
    """A sidebar page. `refresh()` is called every time the page is shown."""
    title = ""

    def __init__(self, ctx, main=None):
        super().__init__()
        self.ctx = ctx
        self.main = main

    def refresh(self) -> None:  # pragma: no cover - overridden
        pass
