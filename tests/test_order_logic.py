from datetime import datetime, timedelta, timezone

from artsecure_bot.services.order_logic import (
    calculate_commission,
    is_premium_active,
    payout_amount,
)


def test_calculate_commission_regular() -> None:
    assert calculate_commission(10000, is_premium_artist=False, base_pct=10) == 1000


def test_calculate_commission_premium() -> None:
    assert calculate_commission(10000, is_premium_artist=True, base_pct=10) == 0


def test_payout_amount() -> None:
    assert payout_amount(10000, 1500) == 8500


def test_is_premium_active_true() -> None:
    future = datetime.now(timezone.utc) + timedelta(days=1)
    assert is_premium_active(future)


def test_is_premium_active_false() -> None:
    past = datetime.now(timezone.utc) - timedelta(days=1)
    assert not is_premium_active(past)
