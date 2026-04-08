from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN

from aiogram import Bot
from sqlalchemy import select

from artsecure_bot.config import Settings
from artsecure_bot.db import session_scope
from artsecure_bot.i18n import tr
from artsecure_bot.models import Order, OrderStatus
from artsecure_bot.payments import (
    ManualRateProvider,
    PaymentEscrowService,
    PayoutConfigError,
    PayoutTransferError,
    send_usdt_from_escrow,
    send_usdt_from_escrow_batch,
)
from artsecure_bot.services.repository import (
    delete_order_with_related,
    get_latest_confirmed_invoice_for_order,
    get_order_by_id,
    get_user_language,
)

logger = logging.getLogger(__name__)
_IN_PROGRESS_ORDER_IDS: set[int] = set()


def _to_aware_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


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
    return PaymentEscrowService(
        wallet_address=settings.escrow_wallet_address,
        invoice_ttl_minutes=settings.payment_invoice_ttl_minutes,
        tolerance_bps=settings.payment_tolerance_bps,
        rate_provider=_build_rate_provider(settings),
        provider_name=settings.payment_provider_name,
    )


def _calculate_payout_amount_usdt(expected_amount_usdt: str, commission_pct: int) -> Decimal:
    expected = Decimal(expected_amount_usdt)
    pct = max(0, min(commission_pct, 100))
    multiplier = Decimal("1") - (Decimal(pct) / Decimal("100"))
    return (expected * multiplier).quantize(Decimal("0.000001"), rounding=ROUND_DOWN)


def _calculate_fee_amount_usdt(expected_amount_usdt: str, payout_amount_usdt: Decimal) -> Decimal:
    expected = Decimal(expected_amount_usdt)
    fee = (expected - payout_amount_usdt).quantize(Decimal("0.000001"), rounding=ROUND_DOWN)
    return max(fee, Decimal("0"))


async def _list_due_order_ids() -> list[int]:
    now = datetime.now(timezone.utc)
    async with session_scope() as session:
        rows = await session.scalars(
            select(Order.id)
            .where(Order.status == OrderStatus.PENDING_REVIEW)
            .where(Order.review_deadline_at.is_not(None))
            .where(Order.review_deadline_at <= now)
            .limit(20)
        )
        return list(rows)


async def _finalize_due_order(bot: Bot, settings: Settings, order_id: int) -> None:
    customer_tg: int | None = None
    artist_tg: int | None = None
    customer_lang = "ru"
    artist_lang = "ru"
    payout_amount_usdt: str | None = None
    payout_tx_hash: str | None = None
    payout_auto_failed = False
    retry_later = False

    async with session_scope() as session:
        order = await get_order_by_id(session, order_id)
        if order is None or order.status != OrderStatus.PENDING_REVIEW:
            return

        deadline = _to_aware_utc(order.review_deadline_at)
        if deadline is None or deadline > datetime.now(timezone.utc):
            return

        customer_tg = order.customer.tg_id
        artist_tg = order.artist.tg_id
        customer_lang = await get_user_language(session, customer_tg)
        artist_lang = await get_user_language(session, artist_tg)

        confirmed_invoice = await get_latest_confirmed_invoice_for_order(session, order.id)
        if confirmed_invoice is None:
            order.status = OrderStatus.FINAL_REVIEW
            order.customer_done = False
            order.artist_done = False
            order.review_deadline_at = None
            await session.flush()
            retry_later = True
        else:
            payout_completed = False
            payout_amount = _calculate_payout_amount_usdt(
                confirmed_invoice.expected_amount_usdt,
                order.commission_pct,
            )
            fee_amount = _calculate_fee_amount_usdt(confirmed_invoice.expected_amount_usdt, payout_amount)
            payout_amount_usdt = f"{payout_amount:.6f}"
            payout_memo = f"order#{order.id}:release"

            if settings.payments_mode == "ton":
                try:
                    if fee_amount > Decimal("0"):
                        fee_amount_usdt = f"{fee_amount:.6f}"
                        payout_tx_hash = await send_usdt_from_escrow_batch(
                            settings=settings,
                            transfers=[
                                (order.artist.wallet_address or "", payout_amount_usdt, payout_memo),
                                (settings.cold_wallet_address, fee_amount_usdt, f"order#{order.id}:fee"),
                            ],
                        )
                    else:
                        payout_tx_hash = await send_usdt_from_escrow(
                            settings=settings,
                            destination_wallet=order.artist.wallet_address or "",
                            amount_usdt=payout_amount_usdt,
                            memo=payout_memo,
                        )
                except (PayoutConfigError, PayoutTransferError) as exc:
                    logger.exception(
                        "Auto review payout failed for order_id=%s invoice_id=%s: %s",
                        order.id,
                        confirmed_invoice.id,
                        exc,
                    )
                    payout_auto_failed = True
                if not payout_auto_failed and payout_tx_hash is not None:
                    payout_completed = True
            else:
                payout_tx_hash = f"mock-release-{confirmed_invoice.id}-{order.id}"
                payout_completed = True

            if not payout_completed or payout_tx_hash is None or payout_amount_usdt is None:
                order.status = OrderStatus.FINAL_REVIEW
                order.customer_done = False
                order.artist_done = False
                order.review_deadline_at = None
                await session.flush()
                retry_later = True
            else:
                payment_service = _build_payment_service(settings)
                await payment_service.mark_released_mock(
                    session,
                    invoice=confirmed_invoice,
                    payout_amount_usdt=payout_amount_usdt,
                    tx_hash=payout_tx_hash,
                )

                order.status = OrderStatus.COMPLETED
                order.customer_done = True
                order.artist_done = True
                order.review_deadline_at = None
                await session.flush()

    if customer_tg is None or artist_tg is None:
        return

    if retry_later:
        await bot.send_message(
            customer_tg,
            tr("relay_payout_retry_later", customer_lang, done_label=tr("btn_mark_done", customer_lang)),
        )
        await bot.send_message(
            artist_tg,
            tr("relay_payout_retry_later", artist_lang, done_label=tr("btn_mark_done", artist_lang)),
        )
        return

    if payout_amount_usdt is None or payout_tx_hash is None:
        return

    await bot.send_message(
        customer_tg,
        tr("relay_payout_customer", customer_lang, amount_usdt=payout_amount_usdt, tx_hash=payout_tx_hash),
    )
    await bot.send_message(
        artist_tg,
        tr("relay_payout_artist", artist_lang, amount_usdt=payout_amount_usdt, tx_hash=payout_tx_hash),
    )

    async with session_scope() as session:
        await delete_order_with_related(session, order_id)


async def run_review_watchdog(bot: Bot, settings: Settings) -> None:
    while True:
        try:
            due_order_ids = await _list_due_order_ids()
            for order_id in due_order_ids:
                if order_id in _IN_PROGRESS_ORDER_IDS:
                    continue
                _IN_PROGRESS_ORDER_IDS.add(order_id)
                try:
                    await _finalize_due_order(bot, settings, order_id)
                finally:
                    _IN_PROGRESS_ORDER_IDS.discard(order_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Review watchdog tick failed")

        await asyncio.sleep(settings.escrow_review_poll_seconds)
