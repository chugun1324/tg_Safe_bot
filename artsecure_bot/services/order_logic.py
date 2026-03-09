from __future__ import annotations

from datetime import datetime, timezone

from artsecure_bot.models import OrderStatus


STATUS_LABELS: dict[OrderStatus, str] = {
    OrderStatus.PENDING_ARTIST: "Ожидает ответа исполнителя",
    OrderStatus.IN_PROGRESS: "В работе",
    OrderStatus.PREVIEW_SENT: "Предпросмотр отправлен",
    OrderStatus.PAID_ESCROW: "Escrow оплачен",
    OrderStatus.FINAL_REVIEW: "Финальная проверка",
    OrderStatus.COMPLETED: "Завершен",
    OrderStatus.DISPUTED: "Спор",
    OrderStatus.CANCELLED: "Отменен",
}


def calculate_commission(price_rub: int, is_premium_artist: bool, base_pct: int = 10) -> int:
    if price_rub <= 0:
        return 0
    if is_premium_artist:
        return 0
    return round(price_rub * base_pct / 100)


def payout_amount(price_rub: int, commission_rub: int) -> int:
    return max(price_rub - commission_rub, 0)


def is_premium_active(premium_until: datetime | None) -> bool:
    if premium_until is None:
        return False
    return premium_until >= datetime.now(timezone.utc)


def status_label(status: OrderStatus) -> str:
    return STATUS_LABELS.get(status, status.value)
