"""Helpers shared by services."""
from __future__ import annotations

import json
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from bejitech.core.timeutil import utcnow_iso
from bejitech.db.models import AuditLog, ReferenceSequence, Setting

REF_FORMATS = {
    "INV": ("INV-{year}-{n:05d}", True),
    "SAL": ("SAL-{year}-{n:05d}", True),
    "DN": ("DN-{year}-{n:05d}", True),
    "CUS": ("CUS-{n:05d}", False),
}


def next_reference(s: Session, prefix: str, on: date | None = None) -> str:
    """Gap-free reference numbers. Must be called inside the caller's transaction."""
    fmt, yearly = REF_FORMATS[prefix]
    year = (on or date.today()).year if yearly else 0
    seq = s.get(ReferenceSequence, (prefix, year))
    if seq is None:
        seq = ReferenceSequence(prefix=prefix, year=year, next_value=1)
        s.add(seq)
        s.flush()
    n = seq.next_value
    seq.next_value = n + 1
    return fmt.format(year=year, n=n)


def audit(s: Session, user_id: int | None, action: str, entity_type: str | None = None,
          entity_uuid: str | None = None, **details) -> None:
    s.add(AuditLog(
        occurred_at=utcnow_iso(), user_id=user_id, action=action, entity_type=entity_type,
        entity_uuid=entity_uuid, details=json.dumps(details, default=str) if details else None,
    ))


def get_setting(s: Session, key: str, default: str = "") -> str:
    row = s.get(Setting, key)
    return row.value if row else default


def set_setting(s: Session, key: str, value: str) -> None:
    row = s.get(Setting, key)
    if row:
        row.value = value
        row.updated_at = utcnow_iso()
    else:
        s.add(Setting(key=key, value=value, updated_at=utcnow_iso()))


def clean(text: str | None) -> str | None:
    if text is None:
        return None
    text = text.strip()
    return text or None


def all_settings(s: Session) -> dict[str, str]:
    return {r.key: r.value for r in s.scalars(select(Setting))}
