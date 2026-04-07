from __future__ import annotations

import io
import logging
import os
import secrets
import zipfile
from decimal import Decimal, ROUND_DOWN
from time import monotonic

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, Message

from artsecure_bot.config import Settings
from artsecure_bot.db import session_scope
from artsecure_bot.handlers.utils import build_main_menu_for_user, require_registered_user
from artsecure_bot.i18n import tr, variants
from artsecure_bot.keyboards import art_kind_keyboard
from artsecure_bot.keyboards import relay_menu
from artsecure_bot.models import ArtAsset, ArtKind, OrderStatus
from artsecure_bot.payments import (
    ManualRateProvider,
    PaymentEscrowService,
    PayoutConfigError,
    PayoutTransferError,
    send_usdt_from_escrow_batch,
    send_usdt_from_escrow,
)
from artsecure_bot.services.chat_cleanup import clear_chat_keep_message
from artsecure_bot.services.repository import (
    delete_order_with_related,
    get_latest_confirmed_invoice_for_order,
    get_order_by_id,
    get_user_language,
    list_orders_for_user,
)
from artsecure_bot.states import RelayState, SendArtState

router = Router()
logger = logging.getLogger(__name__)
_PAYOUT_IN_PROGRESS_ORDER_IDS: dict[int, float] = {}
_PAYOUT_IN_PROGRESS_TTL_SECONDS = 300.0


def _extract_order_id(message: Message) -> int | None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].isdigit():
        return None
    return int(parts[1])


def _extract_media_file_id(message: Message) -> str | None:
    if message.photo:
        return message.photo[-1].file_id
    if message.document:
        return message.document.file_id
    if message.video:
        return message.video.file_id
    if message.animation:
        return message.animation.file_id
    if message.audio:
        return message.audio.file_id
    if message.voice:
        return message.voice.file_id
    if message.video_note:
        return message.video_note.file_id
    return None


def _extract_media_file_id_from_message(message: Message) -> str | None:
    # For sent/copied messages (bot-side) use the same extraction.
    return _extract_media_file_id(message)


def _relay_available(status: OrderStatus) -> bool:
    return status in {
        OrderStatus.IN_PROGRESS,
        OrderStatus.PREVIEW_SENT,
        OrderStatus.PAID_ESCROW,
        OrderStatus.FINAL_REVIEW,
        OrderStatus.DISPUTED,
    }


def _relay_menu_for_user(lang: str, is_artist: bool, status: OrderStatus):
    can_send_art = is_artist and status in {
        OrderStatus.IN_PROGRESS,
        OrderStatus.PREVIEW_SENT,
        OrderStatus.PAID_ESCROW,
        OrderStatus.FINAL_REVIEW,
    }
    can_mark_done = status in {OrderStatus.PAID_ESCROW, OrderStatus.FINAL_REVIEW}
    return relay_menu(language=lang, can_send_art=can_send_art, can_mark_done=can_mark_done)


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


def _calculate_payout_amount_usdt(expected_amount_usdt: str, commission_pct: int) -> Decimal:
    expected = Decimal(expected_amount_usdt)
    pct = max(0, min(commission_pct, 100))
    multiplier = Decimal("1") - (Decimal(pct) / Decimal("100"))
    return (expected * multiplier).quantize(Decimal("0.000001"), rounding=ROUND_DOWN)


def _calculate_fee_amount_usdt(expected_amount_usdt: str, payout_amount_usdt: Decimal) -> Decimal:
    expected = Decimal(expected_amount_usdt)
    fee = (expected - payout_amount_usdt).quantize(Decimal("0.000001"), rounding=ROUND_DOWN)
    return max(fee, Decimal("0"))


async def _build_originals_zip(bot, order_id: int, assets: list[ArtAsset]) -> bytes | None:
    if not assets:
        return None

    out = io.BytesIO()
    added = 0
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_STORED) as zipf:
        for asset in assets:
            file_id = asset.original_file_id or asset.watermarked_file_id
            if not file_id:
                continue
            try:
                file = await bot.get_file(file_id)
                raw = io.BytesIO()
                await bot.download_file(file.file_path, destination=raw)
            except Exception:
                # Fallback to watermarked if original fails.
                if asset.original_file_id and asset.watermarked_file_id and file_id == asset.original_file_id:
                    try:
                        file = await bot.get_file(asset.watermarked_file_id)
                        raw = io.BytesIO()
                        await bot.download_file(file.file_path, destination=raw)
                    except Exception:
                        continue
                else:
                    continue

            ext = os.path.splitext(file.file_path or "")[1] or ".bin"
            filename = f"order_{order_id}_asset_{asset.id}{ext}"
            zipf.writestr(filename, raw.getvalue())
            added += 1

    if added == 0:
        return None
    return out.getvalue()


@router.message(Command("relay"))
async def relay_start(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return

    async with session_scope() as session:
        lang = await get_user_language(session, message.from_user.id)
        order_id = _extract_order_id(message)
        if order_id is None:
            await message.answer(tr("relay_usage", lang))
            return

        user = await require_registered_user(message, session)
        if user is None:
            return

        order = await get_order_by_id(session, order_id)
        if order is None:
            await message.answer(tr("order_not_found", lang))
            return
        if order.status in {OrderStatus.IN_PROGRESS, OrderStatus.PREVIEW_SENT}:
            confirmed_invoice = await get_latest_confirmed_invoice_for_order(session, order.id)
            if confirmed_invoice is not None:
                order.status = OrderStatus.PAID_ESCROW

        if user.id not in {order.customer_id, order.artist_id}:
            await message.answer(tr("dispute_not_participant", lang))
            return

        if order.status in {OrderStatus.CANCELLED, OrderStatus.COMPLETED}:
            await message.answer(tr("relay_order_closed", lang))
            return
        if not _relay_available(order.status):
            await message.answer(tr("relay_not_available_status", lang))
            return

        is_artist = user.id == order.artist_id
        menu = _relay_menu_for_user(lang, is_artist, order.status)

    await state.clear()
    await state.set_state(RelayState.waiting_message)
    await state.update_data(order_id=order_id)
    notice = await message.answer(
        tr("relay_activated", lang, order_id=order_id, leave_label=tr("btn_leave_relay", lang)),
        reply_markup=menu,
    )
    await clear_chat_keep_message(message.bot, message.chat.id, notice.message_id)


@router.message(Command("leave_relay"))
@router.message(F.text.in_(variants("btn_leave_relay")))
async def relay_leave(message: Message, state: FSMContext) -> None:
    await state.clear()
    if message.from_user is None:
        return
    sender_id: int | None = None
    async with session_scope() as session:
        user = await require_registered_user(message, session)
        if user is None:
            return
        lang = await get_user_language(session, user.tg_id)
        menu = await build_main_menu_for_user(session, user)
    await message.answer(tr("relay_off", lang), reply_markup=menu)


@router.message(RelayState.waiting_message, F.text.in_(variants("btn_mark_done")))
@router.message(RelayState.waiting_message, Command("done"))
async def relay_mark_done(message: Message, state: FSMContext, settings: Settings) -> None:
    if message.from_user is None:
        return

    data = await state.get_data()
    order_id = data.get("order_id")
    if not isinstance(order_id, int):
        async with session_scope() as session:
            lang = await get_user_language(session, message.from_user.id)
        await message.answer(tr("relay_session_expired", lang))
        await state.clear()
        return

    archive_bytes: bytes | None = None
    completed_now = False
    customer_tg: int | None = None
    artist_tg: int | None = None
    payout_amount_usdt: str | None = None
    payout_tx_hash: str | None = None
    payout_auto_failed = False
    fee_amount_usdt: str | None = None
    fee_tx_hash: str | None = None

    async with session_scope() as session:
        lang = await get_user_language(session, message.from_user.id)
        user = await require_registered_user(message, session)
        if user is None:
            return

        order = await get_order_by_id(session, order_id)
        if order is None:
            await message.answer(tr("order_not_found", lang))
            await state.clear()
            return

        if order.status in {OrderStatus.CANCELLED, OrderStatus.COMPLETED}:
            await message.answer(tr("relay_order_closed", lang))
            await state.clear()
            return
        if order.status in {OrderStatus.IN_PROGRESS, OrderStatus.PREVIEW_SENT}:
            confirmed_invoice = await get_latest_confirmed_invoice_for_order(session, order.id)
            if confirmed_invoice is not None:
                order.status = OrderStatus.PAID_ESCROW

        if order.status not in {OrderStatus.PAID_ESCROW, OrderStatus.FINAL_REVIEW}:
            await message.answer(tr("relay_done_not_paid", lang))
            return

        retry_finalize = (
            order.customer_done
            and order.artist_done
            and order.status in {OrderStatus.PAID_ESCROW, OrderStatus.FINAL_REVIEW}
        )

        if user.id == order.customer_id:
            if order.customer_done and not retry_finalize:
                await message.answer(tr("relay_done_already", lang))
                return
            order.customer_done = True
            is_artist = False
            other_tg = order.artist.tg_id
        elif user.id == order.artist_id:
            if order.artist_done and not retry_finalize:
                await message.answer(tr("relay_done_already", lang))
                return
            order.artist_done = True
            is_artist = True
            other_tg = order.customer.tg_id
        else:
            await message.answer(tr("relay_not_participant_anymore", lang))
            return

        customer_tg = order.customer.tg_id
        artist_tg = order.artist.tg_id
        with session.no_autoflush:
            customer_lang = await get_user_language(session, customer_tg)
            artist_lang = await get_user_language(session, artist_tg)
            other_lang = await get_user_language(session, other_tg)

        customer_done = "✅" if order.customer_done else "❌"
        artist_done = "✅" if order.artist_done else "❌"

        if order.customer_done and order.artist_done and order.status != OrderStatus.COMPLETED:
            now = monotonic()
            started_at = _PAYOUT_IN_PROGRESS_ORDER_IDS.get(order.id)
            if started_at is not None:
                age = now - started_at
                if age < _PAYOUT_IN_PROGRESS_TTL_SECONDS:
                    logger.info(
                        "Payout already in progress for order_id=%s age_sec=%.1f",
                        order.id,
                        age,
                    )
                    await message.answer(tr("relay_payout_retry_later", lang, done_label=tr("btn_mark_done", lang)))
                    return
                logger.warning(
                    "Payout lock stale for order_id=%s age_sec=%.1f, resetting lock",
                    order.id,
                    age,
                )
                _PAYOUT_IN_PROGRESS_ORDER_IDS.pop(order.id, None)

            _PAYOUT_IN_PROGRESS_ORDER_IDS[order.id] = now
            try:
                payout_completed = False
                # Persist "done" flags and release write lock before long network calls.
                await session.flush()
                await session.commit()
                confirmed_invoice = await get_latest_confirmed_invoice_for_order(session, order.id)
                if confirmed_invoice is not None:
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
                                fee_tx_hash = payout_tx_hash
                            else:
                                payout_tx_hash = await send_usdt_from_escrow(
                                    settings=settings,
                                    destination_wallet=order.artist.wallet_address or "",
                                    amount_usdt=payout_amount_usdt,
                                    memo=payout_memo,
                                )
                        except (PayoutConfigError, PayoutTransferError) as exc:
                            logger.exception(
                                "Auto payout failed for order_id=%s invoice_id=%s: %s",
                                order.id,
                                confirmed_invoice.id,
                                exc,
                            )
                            payout_auto_failed = True
                        if not payout_auto_failed and payout_tx_hash is not None:
                            payout_completed = True
                        if not payout_auto_failed and fee_amount > Decimal("0") and fee_amount_usdt and fee_tx_hash:
                            logger.info(
                                "Fee transfer sent for order_id=%s amount_usdt=%s tx_hash=%s",
                                order.id,
                                fee_amount_usdt,
                                fee_tx_hash,
                            )
                    else:
                        payout_tx_hash = f"mock-release-{confirmed_invoice.id}-{secrets.token_hex(6)}"
                        if fee_amount > Decimal("0"):
                            fee_amount_usdt = f"{fee_amount:.6f}"
                            fee_tx_hash = payout_tx_hash
                        payout_completed = True
                    if payout_completed and payout_tx_hash is not None and payout_amount_usdt is not None:
                        payment_service = _build_payment_service(settings)
                        await payment_service.mark_released_mock(
                            session,
                            invoice=confirmed_invoice,
                            payout_amount_usdt=payout_amount_usdt,
                            tx_hash=payout_tx_hash,
                        )
                else:
                    logger.warning(
                        "No confirmed invoice found for payout order_id=%s status=%s",
                        order.id,
                        order.status.value,
                    )

                if payout_completed:
                    order.status = OrderStatus.COMPLETED
                    await session.flush()
                    await session.commit()
                    archive_bytes = await _build_originals_zip(message.bot, order.id, order.assets)
                    completed_text = tr("relay_done_complete", lang, order_id=order.id)
                    await message.answer(completed_text, reply_markup=_relay_menu_for_user(lang, is_artist, order.status))
                    await message.bot.send_message(
                        other_tg,
                        tr("relay_done_complete", other_lang, order_id=order.id),
                        protect_content=True,
                        reply_markup=_relay_menu_for_user(other_lang, other_tg == artist_tg, order.status),
                    )
                    await state.clear()
                    completed_now = True
                else:
                    order.status = OrderStatus.FINAL_REVIEW
                    await session.flush()
                    await session.commit()
                    await message.answer(
                        tr("relay_payout_retry_later", lang, done_label=tr("btn_mark_done", lang)),
                        reply_markup=_relay_menu_for_user(lang, is_artist, order.status),
                    )
                    await message.bot.send_message(
                        other_tg,
                        tr("relay_payout_retry_later", other_lang, done_label=tr("btn_mark_done", other_lang)),
                        protect_content=True,
                        reply_markup=_relay_menu_for_user(other_lang, other_tg == artist_tg, order.status),
                    )
            finally:
                _PAYOUT_IN_PROGRESS_ORDER_IDS.pop(order.id, None)
        else:
            progress = tr("relay_done_progress", lang, customer_done=customer_done, artist_done=artist_done)
            await message.answer(
                f"{tr('relay_done_marked', lang)}\n{tr('relay_done_wait_other', lang)}\n{progress}",
                reply_markup=_relay_menu_for_user(lang, is_artist, order.status),
            )
            await message.bot.send_message(
                other_tg,
                f"{tr('relay_done_other_confirmed', other_lang, done_label=tr('btn_mark_done', other_lang))}\n"
                f"{tr('relay_done_progress', other_lang, customer_done=customer_done, artist_done=artist_done)}",
                protect_content=True,
                reply_markup=_relay_menu_for_user(other_lang, other_tg == artist_tg, order.status),
            )

    if customer_tg is None or artist_tg is None:
        return

    if completed_now and payout_amount_usdt is not None and payout_tx_hash is not None:
        async with session_scope() as session:
            customer_lang = await get_user_language(session, customer_tg)
            artist_lang = await get_user_language(session, artist_tg)
        if payout_auto_failed:
            await message.bot.send_message(
                customer_tg,
                tr("payout_auto_failed_customer", customer_lang),
                protect_content=True,
            )
            await message.bot.send_message(
                artist_tg,
                tr("payout_auto_failed_artist", artist_lang),
                protect_content=True,
            )
        else:
            await message.bot.send_message(
                customer_tg,
                tr(
                    "relay_payout_customer",
                    customer_lang,
                    amount_usdt=payout_amount_usdt,
                    tx_hash=payout_tx_hash,
                ),
                protect_content=True,
            )
            await message.bot.send_message(
                artist_tg,
                tr(
                    "relay_payout_artist",
                    artist_lang,
                    amount_usdt=payout_amount_usdt,
                    tx_hash=payout_tx_hash,
                ),
                protect_content=True,
            )

    if completed_now and archive_bytes is not None:
        async with session_scope() as session:
            customer_lang = await get_user_language(session, customer_tg)
            artist_lang = await get_user_language(session, artist_tg)
        caption_customer = tr("relay_done_archive_caption", customer_lang, order_id=order_id)
        archive_name = f"order_{order_id}_originals.zip"
        await message.bot.send_document(
            customer_tg,
            BufferedInputFile(archive_bytes, filename=archive_name),
            caption=caption_customer,
            protect_content=True,
        )
        await message.bot.send_message(
            artist_tg,
            tr("relay_done_archive_sent_artist", artist_lang, order_id=order_id),
            protect_content=True,
        )
        async with session_scope() as session:
            await delete_order_with_related(session, order_id)
    elif completed_now:
        async with session_scope() as session:
            customer_lang = await get_user_language(session, customer_tg)
            artist_lang = await get_user_language(session, artist_tg)
        await message.bot.send_message(customer_tg, tr("relay_done_archive_missing", customer_lang))
        await message.bot.send_message(artist_tg, tr("relay_done_archive_missing", artist_lang))
        async with session_scope() as session:
            await delete_order_with_related(session, order_id)


@router.message(F.text.in_(variants("btn_mark_done")))
@router.message(Command("done"))
async def relay_mark_done_fallback(message: Message, state: FSMContext, settings: Settings) -> None:
    if message.from_user is None:
        return
    current_state = await state.get_state()
    if current_state == RelayState.waiting_message.state:
        return

    async with session_scope() as session:
        user = await require_registered_user(message, session)
        if user is None:
            return
        lang = await get_user_language(session, user.tg_id)

        data = await state.get_data()
        order_id = data.get("order_id")
        if not isinstance(order_id, int):
            orders = await list_orders_for_user(session, user)
            candidates: list[int] = []
            for order in orders:
                if user.id not in {order.customer_id, order.artist_id}:
                    continue
                if order.status in {OrderStatus.PAID_ESCROW, OrderStatus.FINAL_REVIEW}:
                    candidates.append(order.id)
                    continue
                if order.status in {OrderStatus.IN_PROGRESS, OrderStatus.PREVIEW_SENT}:
                    confirmed_invoice = await get_latest_confirmed_invoice_for_order(session, order.id)
                    if confirmed_invoice is not None:
                        candidates.append(order.id)

            if len(candidates) == 1:
                order_id = candidates[0]
            elif len(candidates) > 1:
                await message.answer(tr("relay_usage", lang))
                return
            else:
                await message.answer(tr("relay_session_expired", lang))
                return

    await state.set_state(RelayState.waiting_message)
    await state.update_data(order_id=order_id)
    await relay_mark_done(message, state, settings)


@router.message(RelayState.waiting_message, Command("send_art"))
@router.message(RelayState.waiting_message, F.text.in_(variants("btn_send_art")))
async def relay_send_art_entry(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return

    data = await state.get_data()
    order_id = data.get("order_id")

    async with session_scope() as session:
        lang = await get_user_language(session, message.from_user.id)
        if not isinstance(order_id, int):
            await message.answer(tr("relay_session_expired", lang))
            await state.clear()
            return

        user = await require_registered_user(message, session)
        if user is None:
            return

        order = await get_order_by_id(session, order_id)
        if order is None:
            await message.answer(tr("order_not_found", lang))
            await state.clear()
            return

        if user.id != order.artist_id:
            await message.answer(tr("send_art_order_not_yours", lang))
            return

        if order.status in {OrderStatus.CANCELLED, OrderStatus.COMPLETED}:
            menu = await build_main_menu_for_user(session, user)
            await message.answer(tr("relay_order_closed", lang), reply_markup=menu)
            await state.clear()
            return

    await state.set_state(SendArtState.waiting_kind)
    await state.update_data(order_id=order_id)
    await message.answer(tr("send_art_choose_kind", lang), reply_markup=art_kind_keyboard(lang))


@router.message(RelayState.waiting_message)
async def relay_message(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return

    async with session_scope() as session:
        lang = await get_user_language(session, message.from_user.id)

    text = (message.text or "").strip()
    media_file_id = _extract_media_file_id(message)

    if text.startswith("/"):
        await message.answer(tr("relay_use_leave", lang))
        return

    data = await state.get_data()
    order_id = data.get("order_id")
    if not isinstance(order_id, int):
        await message.answer(tr("relay_session_expired", lang))
        await state.clear()
        return

    async with session_scope() as session:
        user = await require_registered_user(message, session)
        if user is None:
            return

        order = await get_order_by_id(session, order_id)
        if order is None:
            await message.answer(tr("order_not_found", lang))
            await state.clear()
            return

        if order.status in {OrderStatus.CANCELLED, OrderStatus.COMPLETED}:
            menu = await build_main_menu_for_user(session, user)
            await message.answer(tr("relay_order_closed", lang), reply_markup=menu)
            await state.clear()
            return

        if user.id == order.customer_id:
            target_tg_id = order.artist.tg_id
            sender_role = tr("relay_sender_customer", lang)
            sender_is_artist = False
            target_is_artist = True
            sender_id = user.id
        elif user.id == order.artist_id:
            target_tg_id = order.customer.tg_id
            sender_role = tr("relay_sender_artist", lang)
            sender_is_artist = True
            target_is_artist = False
            sender_id = user.id
        else:
            await message.answer(tr("relay_not_participant_anymore", lang))
            await state.clear()
            return
        target_lang = await get_user_language(session, target_tg_id)

        sender_menu = _relay_menu_for_user(lang, sender_is_artist, order.status)
        target_menu = _relay_menu_for_user(target_lang, target_is_artist, order.status)

    if text:
        await message.bot.send_message(
            target_tg_id,
            tr(
                "relay_forward",
                target_lang,
                order_id=order_id,
                sender_role=sender_role,
                sender_name=message.from_user.full_name,
                text=text,
            ),
            protect_content=True,
            reply_markup=target_menu,
        )
        return

    if media_file_id is not None:
        if sender_is_artist:
            await message.answer(tr("relay_media_use_send_art", lang), reply_markup=sender_menu)
            return
        await message.bot.send_message(
            target_tg_id,
            tr(
                "relay_media_forward",
                target_lang,
                order_id=order_id,
                sender_role=sender_role,
                sender_name=message.from_user.full_name,
            ),
            protect_content=True,
            reply_markup=target_menu,
        )
        sent_copy = await message.bot.copy_message(
            chat_id=target_tg_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            protect_content=True,
        )
        stored_file_id = _extract_media_file_id_from_message(sent_copy) or media_file_id
        if sender_is_artist and sender_id is not None:
            async with session_scope() as session:
                session.add(
                    ArtAsset(
                        order_id=order_id,
                        sender_id=sender_id,
                        kind=ArtKind.PREVIEW,
                        original_file_id=stored_file_id,
                        watermarked_file_id=None,
                    )
                )
        return

    await message.answer(tr("relay_send_text_or_media", lang), reply_markup=sender_menu)
