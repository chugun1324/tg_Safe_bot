from __future__ import annotations

import re

from aiogram import F, Bot, Dispatcher, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from artsecure_bot.config import Settings
from artsecure_bot.db import session_scope
from artsecure_bot.handlers.utils import build_main_menu_for_user, require_registered_user, require_role
from artsecure_bot.i18n import tr, variants
from artsecure_bot.keyboards import flow_menu, order_actions_keyboard, order_decision_keyboard, relay_menu
from artsecure_bot.models import OrderStatus, UserRole
from artsecure_bot.services.chat_cleanup import clear_chat_keep_message
from artsecure_bot.services.order_logic import status_label
from artsecure_bot.services.repository import (
    create_order,
    delete_order_with_related,
    get_order_by_id,
    get_user_by_tg_id,
    get_user_by_username,
    get_user_language,
    list_orders_for_user,
)
from artsecure_bot.states import CreateOrderState, RelayState

router = Router()
USERNAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]{4,31}$")


def _normalize_username(raw: str) -> str | None:
    normalized = raw.strip().lstrip("@")
    if not USERNAME_PATTERN.fullmatch(normalized):
        return None
    return normalized


async def _username_exists_in_telegram(bot: Bot, username: str) -> bool | None:
    try:
        chat = await bot.get_chat(f"@{username}")
    except TelegramBadRequest:
        return False
    except Exception:
        return None
    return chat.type == "private"


async def _activate_relay_context(state: FSMContext, order_id: int) -> None:
    await state.clear()
    await state.set_state(RelayState.waiting_message)
    await state.update_data(order_id=order_id)


def _relay_menu_for_order(language: str, is_artist: bool, status: OrderStatus):
    can_send_art = is_artist and status in {
        OrderStatus.IN_PROGRESS,
        OrderStatus.PREVIEW_SENT,
        OrderStatus.PAID_ESCROW,
        OrderStatus.FINAL_REVIEW,
    }
    can_mark_done = status in {OrderStatus.PAID_ESCROW, OrderStatus.FINAL_REVIEW}
    return relay_menu(language=language, can_send_art=can_send_art, can_mark_done=can_mark_done)


def _relay_available(status: OrderStatus) -> bool:
    return status in {
        OrderStatus.IN_PROGRESS,
        OrderStatus.PREVIEW_SENT,
        OrderStatus.PAID_ESCROW,
        OrderStatus.FINAL_REVIEW,
        OrderStatus.DISPUTED,
    }


def _parse_callback_order_id(data: str | None, prefix: str) -> int | None:
    if data is None:
        return None
    parts = data.split(":")
    if len(parts) != 2 or parts[0] != prefix or not parts[1].isdigit():
        return None
    return int(parts[1])


@router.message(Command("create"))
@router.message(F.text.in_(variants("btn_create_order")))
async def create_order_start(message: Message, state: FSMContext) -> None:
    async with session_scope() as session:
        customer = await require_role(message, session, UserRole.CUSTOMER)
        if customer is None:
            return
        lang = await get_user_language(session, customer.tg_id)

    await state.clear()
    await state.set_state(CreateOrderState.waiting_artist_username)
    await message.answer(tr("create_ask_artist", lang), reply_markup=flow_menu(lang))


@router.message(CreateOrderState.waiting_artist_username)
async def create_order_artist_username(message: Message, bot: Bot, state: FSMContext) -> None:
    if message.from_user is None:
        return
    raw = message.text or ""
    username = _normalize_username(raw)

    async with session_scope() as session:
        lang = await get_user_language(session, message.from_user.id)
        if username is None:
            await message.answer(tr("username_invalid", lang))
            return

        artist = await get_user_by_username(session, username)

    if artist is None:
        exists = await _username_exists_in_telegram(bot, username)
        if exists is False:
            await message.answer(tr("username_not_exists", lang))
        elif exists is True:
            await message.answer(tr("username_not_registered_artist", lang))
        else:
            await message.answer(tr("username_check_failed", lang))
        return

    if artist.role != UserRole.ARTIST:
        await message.answer(tr("username_not_artist_role", lang))
        return

    await state.update_data(artist_tg_id=artist.tg_id, artist_username=artist.username or username)
    await state.set_state(CreateOrderState.waiting_title)
    await message.answer(tr("create_ask_title", lang), reply_markup=flow_menu(lang))


@router.message(CreateOrderState.waiting_title)
async def create_order_title(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    title = (message.text or "").strip()
    async with session_scope() as session:
        lang = await get_user_language(session, message.from_user.id)
    if len(title) < 3:
        await message.answer(tr("create_title_short", lang))
        return

    await state.update_data(title=title)
    await state.set_state(CreateOrderState.waiting_details)
    await message.answer(tr("create_ask_details", lang), reply_markup=flow_menu(lang))


@router.message(CreateOrderState.waiting_details)
async def create_order_details(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    details = (message.text or "").strip()
    async with session_scope() as session:
        lang = await get_user_language(session, message.from_user.id)
    if len(details) < 5:
        await message.answer(tr("create_details_short", lang))
        return

    await state.update_data(details=details)
    await state.set_state(CreateOrderState.waiting_price)
    await message.answer(tr("create_ask_price", lang), reply_markup=flow_menu(lang))


@router.message(CreateOrderState.waiting_price)
async def create_order_price(message: Message, bot: Bot, state: FSMContext) -> None:
    if message.from_user is None:
        return

    raw = (message.text or "").strip()

    async with session_scope() as session:
        lang = await get_user_language(session, message.from_user.id)
        if not raw.isdigit():
            await message.answer(tr("price_int_only", lang))
            return

        price = int(raw)
        if price <= 0:
            await message.answer(tr("price_positive", lang))
            return

        data = await state.get_data()
        artist_tg_id = data.get("artist_tg_id")
        artist_username = data.get("artist_username")
        title = data.get("title")
        details = data.get("details")

        if not isinstance(artist_tg_id, int) or not title or not details:
            await message.answer(tr("create_expired", lang))
            await state.clear()
            return

        customer = await get_user_by_tg_id(session, message.from_user.id)
        artist = await get_user_by_tg_id(session, int(artist_tg_id))
        if customer is None or artist is None:
            await message.answer(tr("create_user_not_found", lang))
            await state.clear()
            return

        if customer.role != UserRole.CUSTOMER:
            await message.answer(tr("create_only_customer", lang))
            await state.clear()
            return

        artist_lang = await get_user_language(session, artist.tg_id)
        order = await create_order(
            session=session,
            customer_id=customer.id,
            artist_id=artist.id,
            title=title,
            details=details,
            price_rub=price,
        )
        customer_menu = await build_main_menu_for_user(session, customer)

    await state.clear()
    await message.answer(
        tr(
            "create_done",
            lang,
            order_id=order.id,
            artist_username=artist_username or tr("unknown", lang),
            title=title,
            price=price,
        ),
        reply_markup=customer_menu,
    )

    try:
        await bot.send_message(
            artist_tg_id,
            tr(
                "create_send_to_artist",
                artist_lang,
                order_id=order.id,
                customer_name=message.from_user.full_name,
                customer_username=message.from_user.username or tr("no_username", artist_lang),
                title=title,
                details=details,
                price=price,
            ),
            reply_markup=order_decision_keyboard(order.id, artist_lang),
            protect_content=True,
        )
    except Exception:
        await message.answer(tr("create_send_to_artist_failed", lang))


@router.callback_query(F.data.startswith("order_decision:"))
async def order_decision(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    dispatcher: Dispatcher,
) -> None:
    if callback.from_user is None or callback.data is None or callback.message is None:
        return

    parts = callback.data.split(":")
    if len(parts) != 3:
        async with session_scope() as session:
            lang = await get_user_language(session, callback.from_user.id)
        await callback.answer(tr("order_decision_invalid_format", lang), show_alert=True)
        return

    _, order_id_raw, action = parts
    if not order_id_raw.isdigit() or action not in {"accept", "reject"}:
        async with session_scope() as session:
            lang = await get_user_language(session, callback.from_user.id)
        await callback.answer(tr("order_decision_invalid_data", lang), show_alert=True)
        return

    order_id = int(order_id_raw)

    async with session_scope() as session:
        order = await get_order_by_id(session, order_id)
        artist = await get_user_by_tg_id(session, callback.from_user.id)
        artist_lang = await get_user_language(session, callback.from_user.id)
        if order is None or artist is None:
            await callback.answer(tr("order_not_found", artist_lang), show_alert=True)
            return

        if order.artist_id != artist.id:
            await callback.answer(tr("order_not_yours", artist_lang), show_alert=True)
            return

        if order.status != OrderStatus.PENDING_ARTIST:
            await callback.answer(tr("order_already_processed", artist_lang))
            return

        customer_tg = order.customer.tg_id
        customer_lang = await get_user_language(session, customer_tg)
        artist_tg = order.artist.tg_id

        if action == "accept":
            order.status = OrderStatus.IN_PROGRESS
            await callback.answer(tr("order_accept_short", artist_lang))
            await callback.message.edit_reply_markup(reply_markup=None)
        else:
            order.status = OrderStatus.CANCELLED
            await callback.answer(tr("order_reject_short", artist_lang))
            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.message.answer(tr("order_rejected_message", artist_lang))

    if action == "accept":
        await _activate_relay_context(state, order_id)
        customer_state = dispatcher.fsm.get_context(bot=bot, chat_id=customer_tg, user_id=customer_tg)
        await _activate_relay_context(customer_state, order_id)

        artist_notice = await callback.message.answer(
            tr(
                "relay_activated_artist",
                artist_lang,
                order_id=order_id,
                leave_label=tr("btn_leave_relay", artist_lang),
            ),
            reply_markup=relay_menu(artist_lang, can_send_art=True, can_mark_done=False),
        )

        customer_notice = await bot.send_message(
            customer_tg,
            tr(
                "relay_activated_customer",
                customer_lang,
                order_id=order_id,
                leave_label=tr("btn_leave_relay", customer_lang),
            ),
            protect_content=True,
            reply_markup=relay_menu(customer_lang, can_send_art=False, can_mark_done=False),
        )

        await clear_chat_keep_message(bot, artist_tg, artist_notice.message_id)
        await clear_chat_keep_message(bot, customer_tg, customer_notice.message_id)
    else:
        await bot.send_message(
            customer_tg,
            tr("order_rejected_notify_customer", customer_lang, order_id=order_id),
            protect_content=True,
        )


@router.message(Command("my_orders"))
@router.message(F.text.in_(variants("btn_my_orders")))
async def my_orders(message: Message) -> None:
    async with session_scope() as session:
        user = await require_registered_user(message, session)
        if user is None:
            return

        lang = await get_user_language(session, user.tg_id)
        orders = await list_orders_for_user(session, user)
        menu = await build_main_menu_for_user(session, user)

    if not orders:
        await message.answer(tr("my_orders_empty", lang), reply_markup=menu)
        return

    for order in orders:
        text = tr(
            "my_order_card",
            lang,
            order_id=order.id,
            status=status_label(order.status, lang),
            title=order.title,
            price=order.price_rub,
            customer=f"{order.customer.nickname} ({order.customer.tg_id})",
            artist=f"{order.artist.nickname} ({order.artist.tg_id})",
        )
        markup = order_actions_keyboard(order.id, order.status, user.role, lang)
        await message.answer(text, reply_markup=markup)

    await message.answer(tr("my_orders_footer", lang), reply_markup=menu)


def _extract_order_id(message: Message) -> int | None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].isdigit():
        return None
    return int(parts[1])


@router.message(Command("pay"))
async def pay_order(message: Message, bot: Bot) -> None:
    order_id = _extract_order_id(message)
    async with session_scope() as session:
        lang = await get_user_language(session, message.from_user.id if message.from_user else 0)
        if order_id is None:
            await message.answer(tr("usage_pay", lang))
            return

        customer = await require_role(message, session, UserRole.CUSTOMER)
        if customer is None:
            return

        order = await get_order_by_id(session, order_id)
        if order is None:
            await message.answer(tr("order_not_found", lang))
            return

        if order.customer_id != customer.id:
            await message.answer(tr("pay_not_your_order", lang))
            return

        if order.status not in {OrderStatus.IN_PROGRESS, OrderStatus.PREVIEW_SENT}:
            await message.answer(tr("pay_not_available_status", lang))
            return

        order.status = OrderStatus.PAID_ESCROW
        order.customer_done = False
        order.artist_done = False
        order.escrow_amount_rub = order.price_rub
        artist_tg = order.artist.tg_id
        artist_lang = await get_user_language(session, artist_tg)

    await message.answer(
        tr("pay_marked_done", lang, order_id=order_id, done_label=tr("btn_mark_done", lang)),
        reply_markup=relay_menu(lang, can_send_art=False, can_mark_done=True),
    )
    await bot.send_message(
        artist_tg,
        tr("pay_notify_artist", artist_lang, order_id=order_id, price=order.price_rub),
        protect_content=True,
        reply_markup=relay_menu(artist_lang, can_send_art=True, can_mark_done=True),
    )


@router.message(Command("release"))
async def release_order(message: Message) -> None:
    order_id = _extract_order_id(message)
    async with session_scope() as session:
        lang = await get_user_language(session, message.from_user.id if message.from_user else 0)
    if order_id is None:
        await message.answer(tr("usage_release", lang))
        return
    await message.answer(
        tr("release_not_available_status", lang, done_label=tr("btn_mark_done", lang)),
        reply_markup=relay_menu(lang, can_send_art=False, can_mark_done=True),
    )


@router.message(Command("dispute"))
async def dispute_order(message: Message, bot: Bot, settings: Settings) -> None:
    order_id = _extract_order_id(message)
    if message.from_user is None:
        return

    async with session_scope() as session:
        lang = await get_user_language(session, message.from_user.id)
        if order_id is None:
            await message.answer(tr("usage_dispute", lang))
            return

        user = await require_registered_user(message, session)
        if user is None:
            return

        order = await get_order_by_id(session, order_id)
        if order is None:
            await message.answer(tr("order_not_found", lang))
            return

        allowed = user.id in {order.customer_id, order.artist_id} or user.tg_id in settings.admin_ids
        if not allowed:
            await message.answer(tr("dispute_not_participant", lang))
            return

        order.status = OrderStatus.DISPUTED
        customer_tg = order.customer.tg_id
        artist_tg = order.artist.tg_id
        customer_lang = await get_user_language(session, customer_tg)
        artist_lang = await get_user_language(session, artist_tg)

    await message.answer(tr("dispute_opened", lang, order_id=order_id))

    if message.from_user.id != customer_tg:
        await bot.send_message(
            customer_tg, tr("dispute_notify_user", customer_lang, order_id=order_id), protect_content=True
        )
    if message.from_user.id != artist_tg:
        await bot.send_message(
            artist_tg, tr("dispute_notify_user", artist_lang, order_id=order_id), protect_content=True
        )

    for admin_id in settings.admin_ids:
        if admin_id == message.from_user.id:
            continue
        await bot.send_message(
            admin_id,
            tr("dispute_admin_new", lang, order_id=order_id, customer_tg=customer_tg, artist_tg=artist_tg),
        )


@router.message(Command("force_close"))
async def force_close_order(message: Message, bot: Bot) -> None:
    order_id = _extract_order_id(message)
    if message.from_user is None:
        return

    async with session_scope() as session:
        lang = await get_user_language(session, message.from_user.id)
        if order_id is None:
            await message.answer(tr("usage_force_close", lang))
            return

        user = await require_registered_user(message, session)
        if user is None:
            return

        order = await get_order_by_id(session, order_id)
        if order is None:
            await message.answer(tr("order_not_found", lang))
            return

        if user.id not in {order.customer_id, order.artist_id}:
            await message.answer(tr("dispute_not_participant", lang))
            return

        if order.status in {OrderStatus.CANCELLED, OrderStatus.COMPLETED}:
            await message.answer(tr("force_close_already", lang))
            return

        order.status = OrderStatus.CANCELLED
        customer_tg = order.customer.tg_id
        artist_tg = order.artist.tg_id
        customer_lang = await get_user_language(session, customer_tg)
        artist_lang = await get_user_language(session, artist_tg)

    await message.answer(tr("force_close_done", lang, order_id=order_id))
    if message.from_user.id != customer_tg:
        await bot.send_message(
            customer_tg, tr("force_close_notify_other", customer_lang, order_id=order_id)
        )
    if message.from_user.id != artist_tg:
        await bot.send_message(
            artist_tg, tr("force_close_notify_other", artist_lang, order_id=order_id)
        )


@router.callback_query(F.data.startswith("pay:"))
async def pay_callback(callback: CallbackQuery, bot: Bot) -> None:
    if callback.from_user is None or callback.data is None:
        return
    order_id = _parse_callback_order_id(callback.data, "pay")
    if order_id is None:
        return

    async with session_scope() as session:
        lang = await get_user_language(session, callback.from_user.id)
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if user is None:
            await callback.answer(tr("err_not_registered", lang), show_alert=True)
            return
        if user.is_banned:
            await callback.answer(tr("err_banned", lang), show_alert=True)
            return
        if user.role != UserRole.CUSTOMER:
            await callback.answer(tr("err_wrong_role", lang), show_alert=True)
            return

        order = await get_order_by_id(session, order_id)
        if order is None:
            await callback.answer(tr("order_not_found", lang), show_alert=True)
            return
        if order.customer_id != user.id:
            await callback.answer(tr("pay_not_your_order", lang), show_alert=True)
            return
        if order.status not in {OrderStatus.IN_PROGRESS, OrderStatus.PREVIEW_SENT}:
            await callback.answer(tr("pay_not_available_status", lang), show_alert=True)
            return

        order.status = OrderStatus.PAID_ESCROW
        order.customer_done = False
        order.artist_done = False
        order.escrow_amount_rub = order.price_rub
        price_rub = order.price_rub
        artist_tg = order.artist.tg_id
        artist_lang = await get_user_language(session, artist_tg)
        updated_markup = order_actions_keyboard(order.id, order.status, user.role, lang)

    await callback.answer()
    if callback.message is not None:
        await callback.message.edit_reply_markup(reply_markup=updated_markup)
        await callback.message.answer(
            tr("pay_marked_done", lang, order_id=order_id, done_label=tr("btn_mark_done", lang)),
            reply_markup=_relay_menu_for_order(lang, is_artist=False, status=OrderStatus.PAID_ESCROW),
        )
    await bot.send_message(
        artist_tg,
        tr("pay_notify_artist", artist_lang, order_id=order_id, price=price_rub),
        protect_content=True,
        reply_markup=_relay_menu_for_order(artist_lang, is_artist=True, status=OrderStatus.PAID_ESCROW),
    )


@router.callback_query(F.data.startswith("release:"))
async def release_callback(callback: CallbackQuery, bot: Bot) -> None:
    if callback.from_user is None or callback.data is None:
        return
    order_id = _parse_callback_order_id(callback.data, "release")
    if order_id is None:
        return

    async with session_scope() as session:
        lang = await get_user_language(session, callback.from_user.id)
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if user is None:
            await callback.answer(tr("err_not_registered", lang), show_alert=True)
            return
        if user.is_banned:
            await callback.answer(tr("err_banned", lang), show_alert=True)
            return

        order = await get_order_by_id(session, order_id)
        if order is None:
            await callback.answer(tr("order_not_found", lang), show_alert=True)
            return
        if order.customer_id != user.id:
            await callback.answer(tr("pay_not_your_order", lang), show_alert=True)
            return

        order_status = order.status
        updated_markup = order_actions_keyboard(order.id, order.status, user.role, lang)

    await callback.answer()
    if callback.message is not None:
        await callback.message.edit_reply_markup(reply_markup=updated_markup)
        await callback.message.answer(
            tr("release_not_available_status", lang, done_label=tr("btn_mark_done", lang)),
            reply_markup=_relay_menu_for_order(lang, is_artist=False, status=order_status),
        )


@router.callback_query(F.data.startswith("dispute:"))
async def dispute_callback(callback: CallbackQuery, bot: Bot, settings: Settings) -> None:
    if callback.from_user is None or callback.data is None:
        return
    order_id = _parse_callback_order_id(callback.data, "dispute")
    if order_id is None:
        return

    async with session_scope() as session:
        lang = await get_user_language(session, callback.from_user.id)
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if user is None:
            await callback.answer(tr("err_not_registered", lang), show_alert=True)
            return
        if user.is_banned:
            await callback.answer(tr("err_banned", lang), show_alert=True)
            return

        order = await get_order_by_id(session, order_id)
        if order is None:
            await callback.answer(tr("order_not_found", lang), show_alert=True)
            return

        allowed = user.id in {order.customer_id, order.artist_id} or user.tg_id in settings.admin_ids
        if not allowed:
            await callback.answer(tr("dispute_not_participant", lang), show_alert=True)
            return

        if order.status in {OrderStatus.CANCELLED, OrderStatus.COMPLETED}:
            await callback.answer(tr("relay_order_closed", lang), show_alert=True)
            return

        order.status = OrderStatus.DISPUTED
        customer_tg = order.customer.tg_id
        artist_tg = order.artist.tg_id
        customer_lang = await get_user_language(session, customer_tg)
        artist_lang = await get_user_language(session, artist_tg)
        updated_markup = order_actions_keyboard(order.id, order.status, user.role, lang)

    await callback.answer()
    if callback.message is not None:
        await callback.message.edit_reply_markup(reply_markup=updated_markup)
        await callback.message.answer(tr("dispute_opened", lang, order_id=order_id))

    if callback.from_user.id != customer_tg:
        await bot.send_message(
            customer_tg, tr("dispute_notify_user", customer_lang, order_id=order_id), protect_content=True
        )
    if callback.from_user.id != artist_tg:
        await bot.send_message(
            artist_tg, tr("dispute_notify_user", artist_lang, order_id=order_id), protect_content=True
        )

    for admin_id in settings.admin_ids:
        if admin_id == callback.from_user.id:
            continue
        await bot.send_message(
            admin_id,
            tr("dispute_admin_new", lang, order_id=order_id, customer_tg=customer_tg, artist_tg=artist_tg),
        )


@router.callback_query(F.data.startswith("relay_open:"))
async def relay_open_callback(callback: CallbackQuery, bot: Bot, state: FSMContext) -> None:
    if callback.from_user is None or callback.data is None or callback.message is None:
        return
    order_id = _parse_callback_order_id(callback.data, "relay_open")
    if order_id is None:
        return

    async with session_scope() as session:
        lang = await get_user_language(session, callback.from_user.id)
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if user is None:
            await callback.answer(tr("err_not_registered", lang), show_alert=True)
            return
        if user.is_banned:
            await callback.answer(tr("err_banned", lang), show_alert=True)
            return

        order = await get_order_by_id(session, order_id)
        if order is None:
            await callback.answer(tr("order_not_found", lang), show_alert=True)
            return
        if user.id not in {order.customer_id, order.artist_id}:
            await callback.answer(tr("dispute_not_participant", lang), show_alert=True)
            return
        if order.status in {OrderStatus.CANCELLED, OrderStatus.COMPLETED}:
            await callback.answer(tr("relay_order_closed", lang), show_alert=True)
            return
        if not _relay_available(order.status):
            await callback.answer(tr("relay_not_available_status", lang), show_alert=True)
            return

        is_artist = user.id == order.artist_id
        relay_markup = _relay_menu_for_order(lang, is_artist=is_artist, status=order.status)

    await callback.answer()
    await _activate_relay_context(state, order_id)
    notice = await callback.message.answer(
        tr("relay_activated", lang, order_id=order_id, leave_label=tr("btn_leave_relay", lang)),
        reply_markup=relay_markup,
    )
    await clear_chat_keep_message(bot, callback.message.chat.id, notice.message_id)


@router.callback_query(F.data.startswith("delete_order:"))
async def delete_order_callback(callback: CallbackQuery, bot: Bot) -> None:
    if callback.data is None or callback.from_user is None:
        return
    parts = callback.data.split(":")
    if len(parts) != 2 or not parts[1].isdigit():
        return
    order_id = int(parts[1])

    async with session_scope() as session:
        lang = await get_user_language(session, callback.from_user.id)
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if user is None:
            await callback.answer(tr("err_not_registered", lang), show_alert=True)
            return
        if user.is_banned:
            await callback.answer(tr("err_banned", lang), show_alert=True)
            return

        order = await get_order_by_id(session, order_id)
        if order is None:
            await callback.answer(tr("order_not_found", lang), show_alert=True)
            return

        if order.customer_id != user.id:
            await callback.answer(tr("delete_only_customer", lang), show_alert=True)
            return

        artist_tg = order.artist.tg_id
        artist_lang = await get_user_language(session, artist_tg)
        await delete_order_with_related(session, order_id)
        menu = await build_main_menu_for_user(session, user)

    await callback.answer()
    if callback.message is not None:
        await callback.message.answer(tr("delete_order_done", lang, order_id=order_id), reply_markup=menu)
    await bot.send_message(
        artist_tg,
        tr("delete_order_notify_artist", artist_lang, order_id=order_id),
        protect_content=True,
    )
