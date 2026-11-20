"""Money helpers. Amounts are integers in minor units (TZS: shillings, USD: cents)."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from bejitech.core.errors import ValidationError

MINOR_DIGITS = {"TZS": 0, "USD": 2}


def minor_digits(currency: str) -> int:
    return MINOR_DIGITS.get(currency, 2)


def to_minor(amount: str | int | float | Decimal, currency: str = "TZS") -> int:
    """Parse a user-entered amount ('150,000' / '12.50') into minor units."""
    try:
        text = str(amount).replace(",", "").replace(" ", "").strip() or "0"
        value = Decimal(text)
    except InvalidOperation as exc:
        raise ValidationError(f"'{amount}' is not a valid amount.") from exc
    if value < 0:
        raise ValidationError("Amounts cannot be negative.")
    scale = Decimal(10) ** minor_digits(currency)
    return int((value * scale).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def from_minor(minor: int, currency: str = "TZS") -> Decimal:
    return Decimal(minor) / (Decimal(10) ** minor_digits(currency))


def format_money(minor: int | None, currency: str = "TZS", with_code: bool = True) -> str:
    minor = minor or 0
    digits = minor_digits(currency)
    value = from_minor(minor, currency)
    text = f"{value:,.{digits}f}"
    return f"{currency} {text}" if with_code else text


def parse_rate(rate: str | Decimal | float) -> Decimal:
    try:
        value = Decimal(str(rate).replace(",", "").strip())
    except InvalidOperation as exc:
        raise ValidationError(f"'{rate}' is not a valid exchange rate.") from exc
    if value <= 0:
        raise ValidationError("Exchange rate must be greater than zero.")
    return value


def convert_to_tzs(minor: int, currency: str, rate: str | Decimal) -> int:
    """Convert a purchase amount to whole TZS using the given rate (1 unit = rate TZS)."""
    if currency == "TZS":
        return minor
    value = from_minor(minor, currency) * parse_rate(rate)
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def per_unit_cost(total_tzs: int, units: int) -> int:
    if units <= 0:
        return 0
    return int((Decimal(total_tzs) / Decimal(units)).quantize(Decimal(1), rounding=ROUND_HALF_UP))
