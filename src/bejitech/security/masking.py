"""Licence key masking and log redaction."""
from __future__ import annotations

import re

_KEY_PATTERN = re.compile(r"\b[A-Z0-9]{4,6}(?:-[A-Z0-9]{4,6}){3,}\b", re.IGNORECASE)


def normalize_key(key: str) -> str:
    """Canonical form used for fingerprints: upper-case, no surrounding/inner spaces."""
    return re.sub(r"\s+", "", key).upper()


def last_chars(key: str, n: int = 5) -> str:
    compact = normalize_key(key).replace("-", "")
    return compact[-n:]


def mask_key(last: str) -> str:
    return f"XXXXX-XXXXX-XXXXX-XXXXX-{last}"


def redact(text: str) -> str:
    return _KEY_PATTERN.sub("[REDACTED-KEY]", text)
