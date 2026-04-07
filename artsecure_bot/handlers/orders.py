from __future__ import annotations

import re
from decimal import Decimal, ROUND_DOWN
from urllib.parse import quote

from aiogram import F, Bot, Dispatcher, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from artsecure_bot.config import Settings
from artsecure_bot.db import session_scope
from artsecure_bot.handlers.utils import build_main_menu_for_user, require_registered_user, require_role
from artsecure_bot.i18n import tr, variants
from artsecure_bot.keyboards import (
    flow_menu,
    order_actions_keyboard,
    order_currency_keyboard,
    order_decision_keyboard,
    relay_menu,
)
from artsecure_bot.models import OrderStatus, PaymentStatus, UserRole
from artsecure_bot.payments import ManualRateProvider, PaymentEscrowService
from artsecure_bot.services.chat_cleanup import clear_chat_keep_message
from artsecure_bot.services.order_logic import status_label
from artsecure_bot.services.price import format_price_value, order_price_amount, parse_price_input, to_fiat_minor_units
from artsecure_bot.services.repository import (
    create_order,
    delete_order_with_related,
    get_latest_confirmed_invoice_for_order,
    get_latest_open_invoice_for_order,
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


def _build_rate_provider(settings: Settings) -> ManualRateProvider:
    return ManualRateProvider(
        rates_by_currency={
            "RUB": settings.manual_usdt_rate_rub,
            "USD": settings.manual_usdt_rate_usd,
        }
    )


def _build_payment_service(settings: Settings) -> PaymentEscrowService:
    return PaymentEscrowService(
        wallet_address=settings.escrow_wallet_address,
        invoice_ttl_minutes=settings.payment_invoice_ttl_minutes,
        tolerance_bps=settings.payment_tolerance_bps,
        rate_provider=_build_rate_provider(settings),
        provider_name=settings.payment_provider_name,
    )


def _invoice_keyboard(
    invoice_id: int,
    wallet_url: str,
    external_wallet_url: str,
    language: str,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=tr("btn_pay_wallet", language), url=wallet_url)],
            [InlineKeyboardButton(text=tr("btn_pay_tonkeeper", language), url=external_wallet_url)],
            [InlineKeyboardButton(text=tr("btn_invoice_status", language), callback_data=f"invoice_status:{invoice_id}")],
        ]
    )


def _usdt_to_jetton_units(amount_usdt: str) -> int:
    try:
        amount = Decimal(amount_usdt).quantize(Decimal("0.000001"), rounding=ROUND_DOWN)
        units = (amount * Decimal("1000000")).to_integral_value(rounding=ROUND_DOWN)
        return max(int(units), 0)
    except Exception:
        return 0


def _build_wallet_open_url(
    settings: Settings,
    payment_address: str,
    payment_memo: str,
    amount_usdt: str,
) -> str:
    memo = quote(payment_memo, safe="")
    if settings.ton_usdt_jetton_master:
        amount_units = _usdt_to_jetton_units(amount_usdt)
        return (
            f"ton://transfer/{payment_address}"
            f"?jetton={settings.ton_usdt_jetton_master}&amount={amount_units}&text={memo}"
        )
    return f"ton://transfer/{payment_address}?text={memo}"


def _build_external_wallet_url(
    settings: Settings,
    payment_address: str,
    payment_memo: str,
    amount_usdt: str,
) -> str:
    memo = quote(payment_memo, safe="")
    if settings.ton_usdt_jetton_master:
        amount_units = _usdt_to_jetton_units(amount_usdt)
        return (
            f"https://app.tonkeeper.com/transfer/{payment_address}"
            f"?jetton={settings.ton_usdt_jetton_master}&amount={amount_units}&text={memo}"
        )
    return f"https://app.tonkeeper.com/transfer/{payment_address}?text={memo}"


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
    await state.set_state(CreateOrderState.waiting_currency)
    await message.answer(tr("create_ask_currency", lang), reply_markup=order_currency_keyboard(lang))


@router.callback_query(F.data.startswith("order_currency:"), CreateOrderState.waiting_currency)
async def create_order_currency(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None or callback.data is None or callback.message is None:
        return
    async with session_scope() as session:
        lang = await get_user_language(session, callback.from_user.id)
    parts = callback.data.split(":")
    if len(parts) != 2:
        await callback.answer()
        return
    currency = parts[1].upper()
    if currency not in {"RUB", "USD"}:
        await callback.answer(tr("currency_invalid", lang), show_alert=True)
        return

    await state.update_data(price_currency=currency)
    await state.set_state(CreateOrderState.waiting_title)
    await callback.message.answer(
        tr("create_currency_selected", lang, currency=tr(f"currency_{currency.lower()}", lang)),
        reply_markup=flow_menu(lang),
    )
    await callback.answer()


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
    await state.set_state(CreateOrderState.waiting_price)
    data = await state.get_data()
    currency = str(data.get("price_currency", "RUB")).upper()
    await message.answer(
        tr("create_ask_price_currency", lang, currency=tr(f"currency_{currency.lower()}", lang)),
        reply_markup=flow_menu(lang),
    )


@router.message(CreateOrderState.waiting_price)
async def create_order_price(message: Message, bot: Bot, state: FSMContext) -> None:
    if message.from_user is None:
        return

    raw = (message.text or "").strip()

    async with session_scope() as session:
        lang = await get_user_language(session, message.from_user.id)
        price_amount = parse_price_input(raw)
        if price_amount is None:
            await message.answer(tr("price_int_only", lang))
            return

        data = await state.get_data()
        artist_tg_id = data.get("artist_tg_id")
        artist_username = data.get("artist_username")
        title = data.get("title")
        price_currency = str(data.get("price_currency", "RUB")).upper()
        if price_currency not in {"RUB", "USD"}:
            price_currency = "RUB"
        if not isinstance(artist_tg_id, int) or not title:
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
        price_text = format_price_value(price_amount)
        price_int_legacy = int(price_amount.to_integral_value(rounding=ROUND_DOWN))
        order = await create_order(
            session=session,
            customer_id=customer.id,
            artist_id=artist.id,
            title=title,
            details="",
            price_rub=price_int_legacy,
            price_amount=price_text,
            price_currency=price_currency,
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
            price=price_text,
            currency=tr(f"currency_{price_currency.lower()}", lang),
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
                price=price_text,
                currency=tr(f"currency_{price_currency.lower()}", artist_lang),
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
            price=format_price_value(order_price_amount(order)),
            currency=tr(f"currency_{order.price_currency.lower()}", lang),
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
async def pay_order(message: Message, settings: Settings) -> None:
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

        if not settings.escrow_wallet_address:
            await message.answer(tr("payment_wallet_not_configured", lang))
            return
        if not customer.wallet_address:
            await message.answer(tr("wallet_not_connected", lang))
            return

        service = _build_payment_service(settings)
        existing_invoice = await get_latest_open_invoice_for_order(session, order.id)
        if existing_invoice is not None:
            await service.mark_expired_if_needed(session, existing_invoice)
            if existing_invoice.status in {PaymentStatus.CREATED, PaymentStatus.AWAITING_PAYMENT}:
                view = service.as_view(existing_invoice)
            else:
                existing_invoice = None
        if existing_invoice is None:
            invoice = await service.create_invoice(
                session=session,
                order=order,
                customer=customer,
                fiat_currency=order.price_currency,
                fiat_amount_minor=to_fiat_minor_units(order_price_amount(order)),
                payer_wallet_address=customer.wallet_address,
            )
            view = service.as_view(invoice)

    wallet_url = _build_wallet_open_url(
        settings,
        view.payment_address,
        view.payment_memo,
        view.expected_amount_usdt,
    )
    external_wallet_url = _build_external_wallet_url(
        settings,
        view.payment_address,
        view.payment_memo,
        view.expected_amount_usdt,
    )
    await message.answer(
        tr(
            "invoice_created",
            lang,
            invoice_id=view.invoice_id,
            order_id=view.order_id,
            amount_usdt=view.expected_amount_usdt,
            payment_address=view.payment_address,
            payment_memo=view.payment_memo,
            expires_at=view.expires_at.strftime("%Y-%m-%d %H:%M:%S"),
            mode=settings.payments_mode,
        ),
        reply_markup=_invoice_keyboard(view.invoice_id, wallet_url, external_wallet_url, lang),
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

        if order.status != OrderStatus.DISPUTED:
            order.status_before_dispute = order.status
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
        order.status_before_dispute = None
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
async def pay_callback(callback: CallbackQuery, settings: Settings) -> None:
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

        if not settings.escrow_wallet_address:
            await callback.answer(tr("payment_wallet_not_configured", lang), show_alert=True)
            return
        if not user.wallet_address:
            await callback.answer(tr("wallet_not_connected", lang), show_alert=True)
            return

        service = _build_payment_service(settings)
        existing_invoice = await get_latest_open_invoice_for_order(session, order.id)
        if existing_invoice is not None:
            await service.mark_expired_if_needed(session, existing_invoice)
            if existing_invoice.status in {PaymentStatus.CREATED, PaymentStatus.AWAITING_PAYMENT}:
                view = service.as_view(existing_invoice)
            else:
                existing_invoice = None
        if existing_invoice is None:
            invoice = await service.create_invoice(
                session=session,
                order=order,
                customer=user,
                fiat_currency=order.price_currency,
                fiat_amount_minor=to_fiat_minor_units(order_price_amount(order)),
                payer_wallet_address=user.wallet_address,
            )
            view = service.as_view(invoice)
        updated_markup = order_actions_keyboard(order.id, order.status, user.role, lang)

    await callback.answer()
    if callback.message is not None:
        try:
            await callback.message.edit_reply_markup(reply_markup=updated_markup)
        except TelegramBadRequest as exc:
            if "message is not modified" not in str(exc):
                raise
        wallet_url = _build_wallet_open_url(
            settings,
            view.payment_address,
            view.payment_memo,
            view.expected_amount_usdt,
        )
        external_wallet_url = _build_external_wallet_url(
            settings,
            view.payment_address,
            view.payment_memo,
            view.expected_amount_usdt,
        )
        await callback.message.answer(
            tr(
                "invoice_created",
                lang,
                invoice_id=view.invoice_id,
                order_id=view.order_id,
                amount_usdt=view.expected_amount_usdt,
                payment_address=view.payment_address,
                payment_memo=view.payment_memo,
                expires_at=view.expires_at.strftime("%Y-%m-%d %H:%M:%S"),
                mode=settings.payments_mode,
            ),
            reply_markup=_invoice_keyboard(view.invoice_id, wallet_url, external_wallet_url, lang),
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
        try:
            await callback.message.edit_reply_markup(reply_markup=updated_markup)
        except TelegramBadRequest as exc:
            if "message is not modified" not in str(exc):
                raise
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

        if order.status != OrderStatus.DISPUTED:
            order.status_before_dispute = order.status
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
        if order.status in {OrderStatus.IN_PROGRESS, OrderStatus.PREVIEW_SENT}:
            confirmed_invoice = await get_latest_confirmed_invoice_for_order(session, order.id)
            if confirmed_invoice is not None:
                order.status = OrderStatus.PAID_ESCROW
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
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(tr("delete_order_done", lang, order_id=order_id), reply_markup=menu)
    await bot.send_message(
        artist_tg,
        tr("delete_order_notify_artist", artist_lang, order_id=order_id),
        protect_content=True,
    )
