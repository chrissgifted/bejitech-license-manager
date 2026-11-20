"""Authenticator-app codes (TOTP, RFC 6238) for the web version's two-step login."""
from __future__ import annotations

import time

import pyotp

ISSUER = "Bejitech License Manager"
INTERVAL = 30


def new_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(secret: str, username: str) -> str:
    return pyotp.TOTP(secret, interval=INTERVAL).provisioning_uri(name=username, issuer_name=ISSUER)


def verify(secret: str, code: str, now: float | None = None) -> int | None:
    """Return the time step the code belongs to (one step of clock drift allowed), or None."""
    code = "".join(ch for ch in (code or "") if ch.isdigit())
    if len(code) != 6:
        return None
    t = pyotp.TOTP(secret, interval=INTERVAL)
    now = time.time() if now is None else now
    current = int(now // INTERVAL)
    for step in (current, current - 1, current + 1):
        if t.verify(code, for_time=step * INTERVAL, valid_window=0):
            return step
    return None
