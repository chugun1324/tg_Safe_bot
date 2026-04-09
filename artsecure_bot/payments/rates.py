from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


@dataclass(frozen=True)
class RateQuote:
    fiat_currency: str
    amount_fiat_minor: int
    usdt_amount: Decimal
    rate_value: Decimal
    source: str


class ManualRateProvider:
    """Fixed-rate converter for MVP/local tests.

    rates_by_currency means "fiat units per 1 USDT".
    Example: RUB=100, USD=1
    """

    def __init__(self, rates_by_currency: dict[str, float]) -> None:
        self._rates: dict[str, Decimal] = {
            code.upper(): Decimal(str(value))
            for code, value in rates_by_currency.items()
        }

    def quote(self, fiat_currency: str, amount_fiat_minor: int) -> RateQuote:
        if amount_fiat_minor <= 0:
            raise ValueError("amount_fiat_minor must be positive")
        currency = fiat_currency.upper()
        if currency not in self._rates:
            raise ValueError(f"unsupported fiat currency: {currency}")

        amount_fiat = Decimal(amount_fiat_minor) / Decimal("1000000")
        rate = self._rates[currency]
        usdt_amount = (amount_fiat / rate).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
        return RateQuote(
            fiat_currency=currency,
            amount_fiat_minor=amount_fiat_minor,
            usdt_amount=usdt_amount,
            rate_value=rate,
            source="manual",
        )
