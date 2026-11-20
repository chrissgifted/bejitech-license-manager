"""Resolve where the application keeps its data.

macOS:   ~/Library/Application Support/Bejitech License Manager/
Windows: %APPDATA%/Bejitech/Bejitech License Manager/
Set BEJITECH_DATA_DIR to override (used by tests and development).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_data_dir, user_log_dir

from bejitech import APP_NAME


@dataclass(frozen=True)
class AppPaths:
    root: Path
    logs: Path
    # Web version: a postgresql:// URL. None = the SQLite file below (desktop app).
    database_url: str | None = None

    @property
    def database_target(self) -> "Path | str":
        return self.database_url or self.database

    @property
    def database(self) -> Path:
        return self.root / "bejitech.db"

    @property
    def logos(self) -> Path:
        return self.root / "logos"

    @property
    def delivery_notes(self) -> Path:
        return self.root / "delivery_notes"

    @property
    def backups(self) -> Path:
        return self.root / "backups"

    @property
    def reports(self) -> Path:
        return self.root / "reports"

    def ensure(self) -> "AppPaths":
        for p in (self.root, self.logs, self.logos, self.delivery_notes, self.backups, self.reports):
            p.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.root, 0o700)
        except OSError:
            pass
        return self


def default_paths() -> AppPaths:
    override = os.environ.get("BEJITECH_DATA_DIR")
    db_url = os.environ.get("BEJITECH_DATABASE_URL") or None
    if override:
        root = Path(override).expanduser()
        return AppPaths(root=root, logs=root / "logs", database_url=db_url)
    return AppPaths(
        root=Path(user_data_dir(APP_NAME, appauthor="Bejitech")),
        logs=Path(user_log_dir(APP_NAME, appauthor="Bejitech")),
    )
