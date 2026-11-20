"""Application entry point."""
from __future__ import annotations

import logging
import sys

from bejitech import APP_NAME, __version__


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv
    if "--self-test" in args:
        from bejitech.selftest import run_self_test
        return run_self_test()
    if "--version" in args:
        print(f"{APP_NAME} {__version__}")
        return 0
    from PySide6.QtGui import QFont, QIcon
    from PySide6.QtWidgets import QApplication, QMessageBox

    from bejitech.config.logging_setup import setup_logging
    from bejitech.config.paths import default_paths
    from bejitech.security.keystore import default_keystore
    from bejitech.services.context import AppContext
    from bejitech.ui.theme import STYLESHEET

    app = QApplication(args)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName("Bejitech")
    app.setStyleSheet(STYLESHEET)
    if sys.platform == "darwin":
        app.setFont(QFont(".AppleSystemUIFont", 13))
    try:
        from importlib import resources
        icon = resources.files("bejitech.resources").joinpath("app_icon.png")
        if icon.is_file():
            app.setWindowIcon(QIcon(str(icon)))
    except Exception:  # noqa: BLE001
        pass

    paths = default_paths().ensure()
    setup_logging(paths.logs)
    log = logging.getLogger("bejitech")
    log.info("Starting %s %s", APP_NAME, __version__)
    try:
        ctx = AppContext.open(paths, default_keystore(paths.root))
    except Exception as exc:  # noqa: BLE001
        log.exception("Could not open database")
        QMessageBox.critical(None, APP_NAME, f"The database could not be opened:\n\n{exc}")
        return 1

    from bejitech.ui.dialogs.auth_dialogs import FirstRunDialog, LoginDialog
    from bejitech.ui.main_window import MainWindow

    dlg = LoginDialog(ctx) if ctx.auth.has_users() else FirstRunDialog(ctx)
    if not dlg.exec():
        return 0
    window = MainWindow(ctx)
    window.show()
    code = app.exec()
    # Destroy Qt widgets (PDF viewer etc.) before Python tears down, avoiding a crash on quit
    window.close()
    window.deleteLater()
    app.processEvents()
    ctx.db.dispose()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
