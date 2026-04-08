from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
import json
from time import monotonic
from urllib.parse import urlencode
from urllib.request import urlopen


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

    def __init__(
        self,
        rates_by_currency: dict[str, float],
        *,
        rate_source: str = "manual",
        cache_ttl_seconds: int = 120,
        request_timeout_seconds: float = 4.0,
    ) -> None:
        self._rates: dict[str, Decimal] = {
            code.upper(): Decimal(str(value))
            for code, value in rates_by_currency.items()
        }
        # 1 USDT = 1 USDT
        self._rates["USDT"] = Decimal("1")
        self._rate_source = rate_source.strip().lower()
        self._cache_ttl_seconds = max(cache_ttl_seconds, 5)
        self._request_timeout_seconds = max(request_timeout_seconds, 1.0)
        self._cached_live_rates: dict[str, Decimal] | None = None
        self._cached_live_rates_ts: float = 0.0

    def _is_live_enabled(self) -> bool:
        return self._rate_source in {"coingecko", "auto"}

    def _fetch_live_rates(self, currencies: list[str]) -> dict[str, Decimal]:
        # Free endpoint: 1 USDT price in selected fiat currencies.
        params = urlencode(
            {
                "ids": "tether",
                "vs_currencies": ",".join(code.lower() for code in currencies),
            }
        )
        url = f"https://api.coingecko.com/api/v3/simple/price?{params}"
        with urlopen(url, timeout=self._request_timeout_seconds) as response:
            payload = response.read().decode("utf-8")
        data = json.loads(payload)
        tether = data.get("tether", {})
        rates: dict[str, Decimal] = {}
        for code in currencies:
            raw = tether.get(code.lower())
            if raw is None:
                continue
            rate = Decimal(str(raw))
            if rate > 0:
                rates[code] = rate
        return rates

    def _get_live_rates_cached(self, currencies: list[str]) -> dict[str, Decimal]:
        now = monotonic()
        if self._cached_live_rates is not None and now - self._cached_live_rates_ts < self._cache_ttl_seconds:
            return self._cached_live_rates
        rates = self._fetch_live_rates(currencies)
        self._cached_live_rates = rates
        self._cached_live_rates_ts = now
        return rates

    def _resolve_rate(self, currency: str) -> tuple[Decimal, str]:
        if currency == "USDT":
            return Decimal("1"), "fixed_usdt"
        if self._is_live_enabled():
            try:
                live_rates = self._get_live_rates_cached([currency])
                live_rate = live_rates.get(currency)
                if live_rate is not None and live_rate > 0:
                    return live_rate, "coingecko"
            except Exception:
                # Fallback to manual rates below.
                pass
        manual_rate = self._rates.get(currency)
        if manual_rate is None:
            raise ValueError(f"unsupported fiat currency: {currency}")
        return manual_rate, "manual"

    def quote(self, fiat_currency: str, amount_fiat_minor: int) -> RateQuote:
        if amount_fiat_minor <= 0:
            raise ValueError("amount_fiat_minor must be positive")
        currency = fiat_currency.upper()
        amount_fiat = Decimal(amount_fiat_minor) / Decimal("1000000")
        rate, source = self._resolve_rate(currency)
        usdt_amount = (amount_fiat / rate).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
        return RateQuote(
            fiat_currency=currency,
            amount_fiat_minor=amount_fiat_minor,
            usdt_amount=usdt_amount,
            rate_value=rate,
            source=source,
        )
