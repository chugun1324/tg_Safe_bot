from __future__ import annotations

import secrets
from decimal import Decimal, ROUND_DOWN
from urllib.parse import quote

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from pytoniq_core import Address

from artsecure_bot.config import Settings
from artsecure_bot.db import session_scope
from artsecure_bot.handlers.utils import build_main_menu_for_user, require_registered_user, require_role
from artsecure_bot.i18n import tr, variants
from artsecure_bot.keyboards import flow_menu
from artsecure_bot.models import OrderStatus, PaymentStatus, UserRole
from artsecure_bot.payments import (
    ManualRateProvider,
    MockWalletGateway,
    PaymentEscrowService,
    TonWalletGateway,
    schedule_invoice_watch,
)
from artsecure_bot.services.price import order_price_amount, to_fiat_minor_units
from artsecure_bot.services.repository import (
    get_invoice_by_id,
    get_latest_open_invoice_for_order,
    get_order_by_id,
    get_user_by_tg_id,
    get_user_language,
)
from artsecure_bot.states import WalletState

router = Router()


def _build_rate_provider(settings: Settings) -> ManualRateProvider:
    return ManualRateProvider(
        rates_by_currency={
            "RUB": settings.manual_usdt_rate_rub,
            "USD": settings.manual_usdt_rate_usd,
            "USDT": 1.0,
        },
        rate_source=settings.payment_rate_source,
    )


def _build_payment_service(settings: Settings) -> PaymentEscrowService:
    rate_provider = _build_rate_provider(settings)
    return PaymentEscrowService(
        wallet_address=settings.escrow_wallet_address,
        invoice_ttl_minutes=settings.payment_invoice_ttl_minutes,
        tolerance_bps=settings.payment_tolerance_bps,
        rate_provider=rate_provider,
        provider_name=settings.payment_provider_name,
    )


def _build_wallet_gateway(settings: Settings):
    if settings.payments_mode == "ton":
        return TonWalletGateway(
            api_url=settings.ton_api_url,
            api_key=settings.ton_api_key,
            usdt_jetton_master=settings.ton_usdt_jetton_master,
        )
    return MockWalletGateway(mock_balance_usdt=settings.mock_wallet_balance_usdt)


def _extract_int_arg(text: str | None) -> int | None:
    parts = (text or "").split(maxsplit=1)
    if len(parts) != 2 or not parts[1].isdigit():
        return None
    return int(parts[1])


def _extract_text_arg(text: str | None) -> str | None:
    parts = (text or "").split(maxsplit=1)
    if len(parts) != 2:
        return None
    value = parts[1].strip()
    if not value:
        return None
    return value


def _looks_like_wallet_address(value: str) -> bool:
    if len(value) < 40:
        return False
    return value.startswith(("EQ", "UQ", "kQ", "0:"))


def _normalize_wallet_address(value: str) -> str | None:
    raw = value.strip()
    if not raw:
        return None
    if not _looks_like_wallet_address(raw):
        return None
    try:
        address = Address(raw)
        return address.to_str(
            is_user_friendly=True,
            is_url_safe=True,
            is_bounceable=True,
            is_test_only=False,
        )
    except Exception:
        return None


async def _wallet_exists(settings: Settings, wallet_address: str) -> bool | None:
    gateway = _build_wallet_gateway(settings)
    if isinstance(gateway, (TonWalletGateway, MockWalletGateway)):
        return await gateway.wallet_exists(wallet_address)
    return None


def _wallet_warning_by_check_result(language: str, exists: bool | None) -> str | None:
    if exists is False:
        return tr("wallet_address_not_found_soft", language)
    if exists is None:
        return tr("wallet_check_unavailable_soft", language)
    return None


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


async def _try_confirm_invoice_from_chain(
    *,
    session,
    settings: Settings,
    invoice,
    order,
) -> str | None:
    if invoice.status not in {
        PaymentStatus.CREATED,
        PaymentStatus.AWAITING_PAYMENT,
        PaymentStatus.PAID_PENDING_CONFIRM,
        PaymentStatus.UNDERPAID,
        PaymentStatus.OVERPAID,
    }:
        return None
    gateway = _build_wallet_gateway(settings)
    transfer = await gateway.find_matching_transfer(
        escrow_wallet=invoice.payment_address,
        payer_wallet=invoice.payer_wallet_address or "",
        memo=invoice.payment_memo,
        expected_amount=Decimal(invoice.expected_amount_usdt),
    )
    if transfer is None:
        return None
    service = _build_payment_service(settings)
    await service.mark_paid_mock(session, invoice=invoice, order=order, tx_hash=transfer.tx_hash)
    return transfer.tx_hash


@router.message(F.text.in_(variants("btn_wallet")))
async def wallet_button(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    async with session_scope() as session:
        lang = await get_user_language(session, message.from_user.id)
        user = await require_registered_user(message, session)
        if user is None:
            return
    await state.set_state(WalletState.waiting_address)
    await message.answer(tr("wallet_enter_prompt", lang), reply_markup=flow_menu(lang))


@router.message(Command("set_wallet"))
async def set_wallet(message: Message, state: FSMContext, settings: Settings) -> None:
    if message.from_user is None:
        return

    raw = _extract_text_arg(message.text)
    async with session_scope() as session:
        lang = await get_user_language(session, message.from_user.id)
        user = await require_registered_user(message, session)
        if user is None:
            return
        if raw is None:
            await state.set_state(WalletState.waiting_address)
            await message.answer(tr("wallet_enter_prompt", lang), reply_markup=flow_menu(lang))
            return
        normalized = _normalize_wallet_address(raw)
        if normalized is None:
            await message.answer(tr("wallet_address_invalid", lang))
            return
        exists = await _wallet_exists(settings, normalized)
        warning = _wallet_warning_by_check_result(lang, exists)
        user.wallet_address = normalized
        menu = await build_main_menu_for_user(session, user)
    await state.clear()
    response = tr("wallet_saved", lang, wallet_address=normalized)
    if warning is not None:
        response = f"{response}\n{warning}"
    await message.answer(response, reply_markup=menu)


WALLET_FLOW_TEXT_VARIANTS = (
    variants("btn_help")
    | variants("btn_rules")
    | variants("btn_cancel")
    | variants("btn_exit")
    | variants("btn_language")
)


@router.message(
    WalletState.waiting_address,
    ~F.text.startswith("/"),
    ~F.text.in_(WALLET_FLOW_TEXT_VARIANTS),
)
async def wallet_set_from_state(message: Message, state: FSMContext, settings: Settings) -> None:
    if message.from_user is None:
        return
    raw = (message.text or "").strip()
    async with session_scope() as session:
        lang = await get_user_language(session, message.from_user.id)
        user = await require_registered_user(message, session)
        if user is None:
            await state.clear()
            return
        normalized = _normalize_wallet_address(raw)
        if normalized is None:
            await message.answer(tr("wallet_address_invalid", lang))
            return
        exists = await _wallet_exists(settings, normalized)
        warning = _wallet_warning_by_check_result(lang, exists)
        user.wallet_address = normalized
        menu = await build_main_menu_for_user(session, user)
    await state.clear()
    response = tr("wallet_saved", lang, wallet_address=normalized)
    if warning is not None:
        response = f"{response}\n{warning}"
    await message.answer(response, reply_markup=menu)


@router.message(Command("wallet"))
async def wallet_info(message: Message) -> None:
    if message.from_user is None:
        return
    async with session_scope() as session:
        lang = await get_user_language(session, message.from_user.id)
        user = await require_registered_user(message, session)
        if user is None:
            return
        if not user.wallet_address:
            await message.answer(tr("wallet_not_connected", lang))
            return
    await message.answer(tr("wallet_connected", lang, wallet_address=user.wallet_address))


@router.message(Command("invoice"))
async def create_invoice(message: Message, settings: Settings) -> None:
    if message.from_user is None:
        return

    order_id = _extract_int_arg(message.text)
    async with session_scope() as session:
        lang = await get_user_language(session, message.from_user.id)
        if order_id is None:
            await message.answer(tr("usage_invoice", lang))
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
                schedule_invoice_watch(message.bot, settings, view.invoice_id)
                return

        invoice = await service.create_invoice(
            session,
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
    schedule_invoice_watch(message.bot, settings, view.invoice_id)


@router.message(Command("invoice_status"))
async def invoice_status(message: Message, settings: Settings) -> None:
    if message.from_user is None:
        return

    invoice_id = _extract_int_arg(message.text)
    async with session_scope() as session:
        lang = await get_user_language(session, message.from_user.id)
        if invoice_id is None:
            await message.answer(tr("usage_invoice_status", lang))
            return

        user = await require_registered_user(message, session)
        if user is None:
            return
        invoice = await get_invoice_by_id(session, invoice_id)
        if invoice is None:
            await message.answer(tr("invoice_not_found", lang))
            return
        order = await get_order_by_id(session, invoice.order_id)
        if order is None:
            await message.answer(tr("order_not_found", lang))
            return
        if user.id not in {order.customer_id, order.artist_id} and user.tg_id not in settings.admin_ids:
            await message.answer(tr("dispute_not_participant", lang))
            return

        checking_notice = await message.answer(tr("invoice_status_checking", lang))

        service = _build_payment_service(settings)
        await service.mark_expired_if_needed(session, invoice)
        tx_hash = await _try_confirm_invoice_from_chain(
            session=session,
            settings=settings,
            invoice=invoice,
            order=order,
        )
        text = tr(
            "invoice_status_card",
            lang,
            invoice_id=invoice.id,
            order_id=invoice.order_id,
            status=invoice.status.value,
            amount_usdt=invoice.expected_amount_usdt,
            payment_memo=invoice.payment_memo,
            tx_hash=invoice.tx_hash or "-",
            expires_at=invoice.expires_at.strftime("%Y-%m-%d %H:%M:%S"),
        )
        artist_tg = order.artist.tg_id
        customer_tg = order.customer.tg_id
        artist_lang = await get_user_language(session, artist_tg)
        customer_lang = await get_user_language(session, customer_tg)

    try:
        await checking_notice.delete()
    except Exception:
        pass
    await message.answer(text)
    if tx_hash is not None:
        if message.from_user.id != customer_tg:
            await message.bot.send_message(
                customer_tg,
                tr("invoice_paid_notify_customer", customer_lang, order_id=order.id, tx_hash=tx_hash),
            )
        await message.bot.send_message(
            artist_tg,
            tr("invoice_paid_notify_artist", artist_lang, order_id=order.id, tx_hash=tx_hash),
        )


@router.callback_query(F.data.startswith("invoice_status:"))
async def invoice_status_callback(callback: CallbackQuery, settings: Settings) -> None:
    if callback.from_user is None or callback.data is None:
        return
    parts = callback.data.split(":")
    if len(parts) != 2 or not parts[1].isdigit():
        await callback.answer()
        return
    invoice_id = int(parts[1])

    async with session_scope() as session:
        lang = await get_user_language(session, callback.from_user.id)
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if user is None:
            await callback.answer(tr("err_not_registered", lang), show_alert=True)
            return
        if user.is_banned:
            await callback.answer(tr("err_banned", lang), show_alert=True)
            return
        invoice = await get_invoice_by_id(session, invoice_id)
        if invoice is None:
            await callback.answer(tr("invoice_not_found", lang), show_alert=True)
            return
        order = await get_order_by_id(session, invoice.order_id)
        if order is None:
            await callback.answer(tr("order_not_found", lang), show_alert=True)
            return
        if user.id not in {order.customer_id, order.artist_id} and user.tg_id not in settings.admin_ids:
            await callback.answer(tr("dispute_not_participant", lang), show_alert=True)
            return
        await callback.answer()
        checking_notice = None
        if callback.message is not None:
            checking_notice = await callback.message.answer(tr("invoice_status_checking", lang))

        service = _build_payment_service(settings)
        await service.mark_expired_if_needed(session, invoice)
        tx_hash = await _try_confirm_invoice_from_chain(
            session=session,
            settings=settings,
            invoice=invoice,
            order=order,
        )
        text = tr(
            "invoice_status_card",
            lang,
            invoice_id=invoice.id,
            order_id=invoice.order_id,
            status=invoice.status.value,
            amount_usdt=invoice.expected_amount_usdt,
            payment_memo=invoice.payment_memo,
            tx_hash=invoice.tx_hash or "-",
            expires_at=invoice.expires_at.strftime("%Y-%m-%d %H:%M:%S"),
        )
        artist_tg = order.artist.tg_id
        customer_tg = order.customer.tg_id
        artist_lang = await get_user_language(session, artist_tg)
        customer_lang = await get_user_language(session, customer_tg)
    if callback.message is not None:
        try:
            if checking_notice is not None:
                await checking_notice.delete()
        except Exception:
            pass
        await callback.message.answer(text)
    if tx_hash is not None:
        if callback.from_user.id != customer_tg:
            await callback.bot.send_message(
                customer_tg,
                tr("invoice_paid_notify_customer", customer_lang, order_id=order.id, tx_hash=tx_hash),
            )
        await callback.bot.send_message(
            artist_tg,
            tr("invoice_paid_notify_artist", artist_lang, order_id=order.id, tx_hash=tx_hash),
        )
    try:
        await callback.answer()
    except TelegramBadRequest:
        pass


@router.message(Command("mock_paid"))
async def mock_paid(message: Message, bot: Bot, settings: Settings) -> None:
    if message.from_user is None:
        return

    invoice_id = _extract_int_arg(message.text)
    async with session_scope() as session:
        lang = await get_user_language(session, message.from_user.id)
        if settings.payments_mode != "mock":
            await message.answer(tr("mock_only_mode", lang))
            return
        if invoice_id is None:
            await message.answer(tr("usage_mock_paid", lang))
            return
        actor = await require_registered_user(message, session)
        if actor is None:
            return

        invoice = await get_invoice_by_id(session, invoice_id)
        if invoice is None:
            await message.answer(tr("invoice_not_found", lang))
            return
        order = await get_order_by_id(session, invoice.order_id)
        if order is None:
            await message.answer(tr("order_not_found", lang))
            return
        if actor.id != order.customer_id and actor.tg_id not in settings.admin_ids:
            await message.answer(tr("pay_not_your_order", lang))
            return

        service = _build_payment_service(settings)
        tx_hash = f"mock-{invoice.id}-{secrets.token_hex(6)}"
        await service.mark_paid_mock(session, invoice=invoice, order=order, tx_hash=tx_hash)

        customer_tg = order.customer.tg_id
        artist_tg = order.artist.tg_id
        artist_lang = await get_user_language(session, artist_tg)

    await message.answer(
        tr("mock_paid_done", lang, invoice_id=invoice.id, order_id=order.id, tx_hash=tx_hash)
    )
    if artist_tg != customer_tg:
        await bot.send_message(
            artist_tg,
            tr("mock_paid_notify_artist", artist_lang, order_id=order.id),
            protect_content=True,
        )
