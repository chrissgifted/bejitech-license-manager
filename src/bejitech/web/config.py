"""Web server settings, all read from environment variables (set on the hosting service).

BEJITECH_DATABASE_URL   postgresql://… connection string (Render gives you this). Leave empty to use
                        a SQLite file in BEJITECH_DATA_DIR (local trials only).
BEJITECH_DATA_DIR       folder for logos and delivery-note PDFs (a persistent disk on Render).
BEJITECH_DEK            the encryption key for licence keys, base64 (python -m bejitech.web genkey).
BEJITECH_SECRET_KEY     signs the login cookie; any long random text (python -m bejitech.web genkey).
BEJITECH_SETUP_TOKEN    one-time code you type when creating the administrator account, so nobody
                        else can claim a fresh server.
BEJITECH_COOKIE_SECURE  "1" (default) sends the login cookie over HTTPS only; "0" for local trials.
BEJITECH_LOCAL_MODE     "1" when running on your own computer (scripts/run_web_local.sh): the setup code
                        is not asked when the administrator is created from that same computer.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WebConfig:
    data_dir: Path
    database_url: str | None
    secret_key: str
    setup_token: str
    cookie_secure: bool = True
    local_mode: bool = False
    session_max_hours: int = 12
    two_step_pending_seconds: int = 300

    @classmethod
    def from_env(cls) -> "WebConfig":
        secret = os.environ.get("BEJITECH_SECRET_KEY", "")
        if len(secret) < 32:
            raise RuntimeError("BEJITECH_SECRET_KEY must be set to a random value of at least 32 characters.")
        return cls(
            data_dir=Path(os.environ.get("BEJITECH_DATA_DIR", "./bejitech-data")).expanduser(),
            database_url=os.environ.get("BEJITECH_DATABASE_URL") or os.environ.get("DATABASE_URL") or None,
            secret_key=secret,
            setup_token=os.environ.get("BEJITECH_SETUP_TOKEN", ""),
            cookie_secure=os.environ.get("BEJITECH_COOKIE_SECURE", "1") != "0",
            local_mode=os.environ.get("BEJITECH_LOCAL_MODE", "0") == "1",
        )
