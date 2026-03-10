from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import Message

from artsecure_bot.config import Settings
from artsecure_bot.db import session_scope
from artsecure_bot.i18n import tr, variants
from artsecure_bot.models import OrderStatus
from artsecure_bot.services.order_logic import calculate_commission, is_premium_active
from artsecure_bot.services.repository import (
    add_to_blacklist,
    get_order_by_id,
    get_stats,
    get_user_by_tg_id,
    get_user_language,
)

router = Router()


def _is_admin(message: Message, settings: Settings) -> bool:
    if message.from_user is None:
        return False
    return message.from_user.id in settings.admin_ids


@router.message(Command("admin_stats"))
@router.message(F.text.in_(variants("btn_admin_stats")))
async def admin_stats(message: Message, settings: Settings) -> None:
    if message.from_user is None:
        return
    async with session_scope() as session:
        lang = await get_user_language(session, message.from_user.id)
        if not _is_admin(message, settings):
            await message.answer(tr("admin_only", lang))
            return
        stats = await get_stats(session)

    await message.answer(
        tr(
            "admin_stats",
            lang,
            total_orders=stats["total_orders"],
            completed_orders=stats["completed_orders"],
            disputed_orders=stats["disputed_orders"],
            gross_rub=stats["gross_rub"],
        )
    )


@router.message(Command("ban"))
async def admin_ban(message: Message, settings: Settings) -> None:
    if message.from_user is None:
        return
    async with session_scope() as session:
        lang = await get_user_language(session, message.from_user.id)
        if not _is_admin(message, settings):
            await message.answer(tr("admin_only", lang))
            return

        parts = (message.text or "").split(maxsplit=2)
        if len(parts) < 3 or not parts[1].isdigit():
            await message.answer(tr("usage_ban", lang))
            return

        tg_id = int(parts[1])
        reason = parts[2].strip()
        user = await get_user_by_tg_id(session, tg_id)
        if user is None:
            await message.answer(tr("user_not_found", lang))
            return

        user.is_banned = True
        await add_to_blacklist(
            session=session,
            user_id=user.id,
            reason=reason,
            created_by_tg_id=message.from_user.id,
        )
        target_lang = await get_user_language(session, tg_id)

    await message.answer(tr("user_banned", lang, tg_id=tg_id))
    await message.bot.send_message(tg_id, tr("user_banned_notify", target_lang, reason=reason))


@router.message(Command("unban"))
async def admin_unban(message: Message, settings: Settings) -> None:
    if message.from_user is None:
        return
    async with session_scope() as session:
        lang = await get_user_language(session, message.from_user.id)
        if not _is_admin(message, settings):
            await message.answer(tr("admin_only", lang))
            return

        parts = (message.text or "").split(maxsplit=1)
        if len(parts) < 2 or not parts[1].isdigit():
            await message.answer(tr("usage_unban", lang))
            return

        tg_id = int(parts[1])
        user = await get_user_by_tg_id(session, tg_id)
        if user is None:
            await message.answer(tr("user_not_found", lang))
            return
        user.is_banned = False

    await message.answer(tr("user_unbanned", lang, tg_id=tg_id))


@router.message(Command("resolve"))
async def admin_resolve(message: Message, bot: Bot, settings: Settings) -> None:
    if message.from_user is None:
        return
    async with session_scope() as session:
        lang = await get_user_language(session, message.from_user.id)
        if not _is_admin(message, settings):
            await message.answer(tr("admin_only", lang))
            return

        parts = (message.text or "").split(maxsplit=2)
        if len(parts) < 3 or not parts[1].isdigit() or parts[2] not in {"refund", "release"}:
            await message.answer(tr("usage_resolve", lang))
            return

        order_id = int(parts[1])
        decision = parts[2]

        order = await get_order_by_id(session, order_id)
        if order is None:
            await message.answer(tr("order_not_found", lang))
            return

        customer_tg = order.customer.tg_id
        artist_tg = order.artist.tg_id
        customer_lang = await get_user_language(session, customer_tg)
        artist_lang = await get_user_language(session, artist_tg)

        if decision == "refund":
            order.status = OrderStatus.CANCELLED
            customer_msg = tr("admin_refund_customer", customer_lang, order_id=order_id)
            artist_msg = tr("admin_refund_artist", artist_lang, order_id=order_id)
        else:
            order.status = OrderStatus.COMPLETED
            commission = calculate_commission(
                order.price_rub,
                is_premium_active(order.artist.premium_until),
                order.commission_pct,
            )
            payout = max(order.price_rub - commission, 0)
            customer_msg = tr("admin_release_customer", customer_lang, order_id=order_id, payout=payout)
            artist_msg = tr("admin_release_artist", artist_lang, order_id=order_id, payout=payout)

    await message.answer(tr("admin_resolve_done", lang, order_id=order_id, decision=decision))
    await bot.send_message(customer_tg, customer_msg)
    await bot.send_message(artist_tg, artist_msg)
