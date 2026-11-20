import pytest

from bejitech.core.errors import ValidationError
from bejitech.core.money import convert_to_tzs, format_money, per_unit_cost, to_minor


def test_parse_tzs_with_separators():
    assert to_minor("150,000") == 150000


def test_parse_usd_cents():
    assert to_minor("12.50", "USD") == 1250


def test_negative_rejected():
    with pytest.raises(ValidationError):
        to_minor("-5")


def test_garbage_rejected():
    with pytest.raises(ValidationError):
        to_minor("abc")


def test_format():
    assert format_money(1850000) == "TZS 1,850,000"
    assert format_money(1250, "USD") == "USD 12.50"


def test_usd_to_tzs_conversion_uses_rate():
    assert convert_to_tzs(1200, "USD", "2650") == 31800
    assert convert_to_tzs(5000, "TZS", "1") == 5000


def test_per_unit_cost_rounds():
    assert per_unit_cost(31800, 5) == 6360
    assert per_unit_cost(10000, 3) == 3333
    assert per_unit_cost(100, 0) == 0
