from __future__ import annotations

import io
import os
import zipfile

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, Message

from artsecure_bot.db import session_scope
from artsecure_bot.handlers.utils import build_main_menu_for_user, require_registered_user
from artsecure_bot.i18n import tr, variants
from artsecure_bot.keyboards import art_kind_keyboard
from artsecure_bot.keyboards import relay_menu
from artsecure_bot.models import ArtAsset, ArtKind, OrderStatus
from artsecure_bot.services.chat_cleanup import clear_chat_keep_message
from artsecure_bot.services.repository import get_order_by_id, get_user_language
from artsecure_bot.states import RelayState, SendArtState

router = Router()


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
async def relay_mark_done(message: Message, state: FSMContext) -> None:
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
    customer_tg: int | None = None
    artist_tg: int | None = None

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

        if order.status not in {OrderStatus.PAID_ESCROW, OrderStatus.FINAL_REVIEW}:
            await message.answer(tr("relay_done_not_paid", lang))
            return

        if user.id == order.customer_id:
            if order.customer_done:
                await message.answer(tr("relay_done_already", lang))
                return
            order.customer_done = True
            is_artist = False
            other_tg = order.artist.tg_id
        elif user.id == order.artist_id:
            if order.artist_done:
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
        customer_lang = await get_user_language(session, customer_tg)
        artist_lang = await get_user_language(session, artist_tg)
        other_lang = await get_user_language(session, other_tg)

        customer_done = "✅" if order.customer_done else "❌"
        artist_done = "✅" if order.artist_done else "❌"

        if order.customer_done and order.artist_done and order.status != OrderStatus.COMPLETED:
            order.status = OrderStatus.COMPLETED
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

    if archive_bytes is not None:
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
    else:
        async with session_scope() as session:
            customer_lang = await get_user_language(session, customer_tg)
            artist_lang = await get_user_language(session, artist_tg)
        await message.bot.send_message(customer_tg, tr("relay_done_archive_missing", customer_lang))
        await message.bot.send_message(artist_tg, tr("relay_done_archive_missing", artist_lang))


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
        await message.answer(tr("relay_sent", lang), reply_markup=sender_menu)
        return

    if media_file_id is not None:
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
        await message.answer(tr("relay_sent", lang), reply_markup=sender_menu)
        return

    await message.answer(tr("relay_send_text_or_media", lang), reply_markup=sender_menu)
