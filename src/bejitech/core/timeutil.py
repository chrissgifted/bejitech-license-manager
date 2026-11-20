from __future__ import annotations

from datetime import date, datetime, timezone


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def today_iso() -> str:
    return date.today().isoformat()


def parse_date(text: str | None) -> date | None:
    if not text:
        return None
    return date.fromisoformat(text[:10])


def display_date(text: str | None) -> str:
    d = parse_date(text)
    return d.strftime("%d %b %Y") if d else "—"


def display_datetime(text: str | None) -> str:
    if not text:
        return "—"
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone()
    except ValueError:
        return text
    return dt.strftime("%d %b %Y %H:%M")
