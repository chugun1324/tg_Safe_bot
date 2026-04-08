from __future__ import annotations

import asyncio
import logging
from decimal import Decimal
from time import monotonic

from aiogram import Bot

from artsecure_bot.config import Settings
from artsecure_bot.db import session_scope
from artsecure_bot.i18n import tr
from artsecure_bot.models import PaymentStatus
from artsecure_bot.payments.gateway import MockWalletGateway, TonWalletGateway
from artsecure_bot.payments.rates import ManualRateProvider
from artsecure_bot.payments.service import PaymentEscrowService
from artsecure_bot.services.repository import get_invoice_by_id, get_order_by_id, get_user_language

logger = logging.getLogger(__name__)

_ACTIVE_WATCHES: set[int] = set()
_WATCH_TIMEOUT_SECONDS = 60 * 60
_WATCH_POLL_SECONDS = 8


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


async def _watch_invoice_task(bot: Bot, settings: Settings, invoice_id: int) -> None:
    started = monotonic()
    try:
        while monotonic() - started < _WATCH_TIMEOUT_SECONDS:
            notify_payload: tuple[int, int, str, str] | None = None

            async with session_scope() as session:
                invoice = await get_invoice_by_id(session, invoice_id)
                if invoice is None:
                    return

                order = await get_order_by_id(session, invoice.order_id)
                if order is None:
                    return

                service = _build_payment_service(settings)
                await service.mark_expired_if_needed(session, invoice)

                if invoice.status in {
                    PaymentStatus.CONFIRMED,
                    PaymentStatus.RELEASED,
                    PaymentStatus.REFUNDED,
                    PaymentStatus.CANCELLED,
                    PaymentStatus.EXPIRED,
                }:
                    return

                tx_hash = await _try_confirm_invoice_from_chain(
                    session=session,
                    settings=settings,
                    invoice=invoice,
                    order=order,
                )
                if tx_hash is not None:
                    notify_payload = (order.id, order.customer.tg_id, order.artist.tg_id, tx_hash)

            if notify_payload is not None:
                order_id, customer_tg, artist_tg, tx_hash = notify_payload
                async with session_scope() as session:
                    customer_lang = await get_user_language(session, customer_tg)
                    artist_lang = await get_user_language(session, artist_tg)
                await bot.send_message(
                    customer_tg,
                    tr("invoice_paid_notify_customer", customer_lang, order_id=order_id, tx_hash=tx_hash),
                )
                await bot.send_message(
                    artist_tg,
                    tr("invoice_paid_notify_artist", artist_lang, order_id=order_id, tx_hash=tx_hash),
                )
                return

            await asyncio.sleep(_WATCH_POLL_SECONDS)
    except Exception:
        logger.exception("Invoice watch failed for invoice_id=%s", invoice_id)
    finally:
        _ACTIVE_WATCHES.discard(invoice_id)


def schedule_invoice_watch(bot: Bot, settings: Settings, invoice_id: int) -> None:
    if invoice_id in _ACTIVE_WATCHES:
        return
    _ACTIVE_WATCHES.add(invoice_id)
    asyncio.create_task(_watch_invoice_task(bot, settings, invoice_id))
