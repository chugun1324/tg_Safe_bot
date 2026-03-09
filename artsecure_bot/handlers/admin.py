from __future__ import annotations

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import Message

from artsecure_bot.config import Settings
from artsecure_bot.db import session_scope
from artsecure_bot.models import OrderStatus
from artsecure_bot.services.order_logic import calculate_commission, is_premium_active
from artsecure_bot.services.repository import (
    add_to_blacklist,
    get_order_by_id,
    get_stats,
    get_user_by_tg_id,
)

router = Router()


def _is_admin(message: Message, settings: Settings) -> bool:
    if message.from_user is None:
        return False
    return message.from_user.id in settings.admin_ids


@router.message(Command("admin_stats"))
async def admin_stats(message: Message, settings: Settings) -> None:
    if not _is_admin(message, settings):
        await message.answer("Команда доступна только администратору.")
        return

    async with session_scope() as session:
        stats = await get_stats(session)

    await message.answer(
        (
            "[ADMIN] Статистика\n"
            f"Всего заказов: {stats['total_orders']}\n"
            f"Завершено: {stats['completed_orders']}\n"
            f"В спорах: {stats['disputed_orders']}\n"
            f"Оборот (gross): {stats['gross_rub']} RUB"
        )
    )


@router.message(Command("ban"))
async def admin_ban(message: Message, settings: Settings) -> None:
    if not _is_admin(message, settings):
        await message.answer("Команда доступна только администратору.")
        return

    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 3 or not parts[1].isdigit():
        await message.answer("Использование: /ban <tg_id> <причина>")
        return

    tg_id = int(parts[1])
    reason = parts[2].strip()

    async with session_scope() as session:
        user = await get_user_by_tg_id(session, tg_id)
        if user is None:
            await message.answer("Пользователь не найден.")
            return

        user.is_banned = True
        await add_to_blacklist(
            session=session,
            user_id=user.id,
            reason=reason,
            created_by_tg_id=message.from_user.id,
        )

    await message.answer(f"Пользователь {tg_id} заблокирован.")
    await message.bot.send_message(tg_id, f"Вы заблокированы в ArtSecure. Причина: {reason}")


@router.message(Command("unban"))
async def admin_unban(message: Message, settings: Settings) -> None:
    if not _is_admin(message, settings):
        await message.answer("Команда доступна только администратору.")
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("Использование: /unban <tg_id>")
        return

    tg_id = int(parts[1])
    async with session_scope() as session:
        user = await get_user_by_tg_id(session, tg_id)
        if user is None:
            await message.answer("Пользователь не найден.")
            return
        user.is_banned = False

    await message.answer(f"Пользователь {tg_id} разблокирован.")


@router.message(Command("resolve"))
async def admin_resolve(message: Message, bot: Bot, settings: Settings) -> None:
    if not _is_admin(message, settings):
        await message.answer("Команда доступна только администратору.")
        return

    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 3 or not parts[1].isdigit() or parts[2] not in {"refund", "release"}:
        await message.answer("Использование: /resolve <order_id> <refund|release>")
        return

    order_id = int(parts[1])
    decision = parts[2]

    async with session_scope() as session:
        order = await get_order_by_id(session, order_id)
        if order is None:
            await message.answer("Заказ не найден.")
            return

        if decision == "refund":
            order.status = OrderStatus.CANCELLED
            customer_msg = f"[ADMIN] Спор по заказу #{order_id} закрыт: возврат средств заказчику."
            artist_msg = f"[ADMIN] Спор по заказу #{order_id} закрыт: средства возвращены заказчику."
        else:
            order.status = OrderStatus.COMPLETED
            commission = calculate_commission(
                order.price_rub,
                is_premium_active(order.artist.premium_until),
                order.commission_pct,
            )
            payout = max(order.price_rub - commission, 0)
            customer_msg = (
                f"[ADMIN] Спор по заказу #{order_id} закрыт: релиз исполнителю ({payout} RUB)."
            )
            artist_msg = (
                f"[ADMIN] Спор по заказу #{order_id} закрыт: релиз средств ({payout} RUB)."
            )

        customer_tg = order.customer.tg_id
        artist_tg = order.artist.tg_id

    await message.answer(f"Спор по заказу #{order_id} закрыт решением: {decision}")
    await bot.send_message(customer_tg, customer_msg)
    await bot.send_message(artist_tg, artist_msg)
