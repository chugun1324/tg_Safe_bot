from __future__ import annotations

import re
from decimal import Decimal, ROUND_DOWN
from typing import Any

PRICE_SCALE = 6
PRICE_MULTIPLIER = Decimal("1000000")
PRICE_INPUT_PATTERN = re.compile(r"^\d+(?:[.,]\d{1,6})?$")


def parse_price_input(raw: str) -> Decimal | None:
    value = raw.strip()
    if not PRICE_INPUT_PATTERN.fullmatch(value):
        return None
    normalized = value.replace(",", ".")
    amount = Decimal(normalized)
    if amount <= 0:
        return None
    return amount.quantize(Decimal("0.000001"), rounding=ROUND_DOWN)


def format_price_value(value: Decimal | int | str | float) -> str:
    amount = Decimal(str(value)).quantize(Decimal("0.000001"), rounding=ROUND_DOWN)
    text = f"{amount:f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def order_price_amount(order: Any) -> Decimal:
    raw = getattr(order, "price_amount", None)
    if raw is not None:
        try:
            amount = Decimal(str(raw))
            if amount > 0:
                return amount.quantize(Decimal("0.000001"), rounding=ROUND_DOWN)
        except Exception:
            pass
    legacy = getattr(order, "price_rub", 0) or 0
    return Decimal(str(legacy)).quantize(Decimal("0.000001"), rounding=ROUND_DOWN)


def to_fiat_minor_units(amount: Decimal) -> int:
    return int((amount * PRICE_MULTIPLIER).to_integral_value(rounding=ROUND_DOWN))
