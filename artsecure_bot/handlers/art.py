from __future__ import annotations

import io

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Document, Message, PhotoSize

from artsecure_bot.db import session_scope
from artsecure_bot.handlers.utils import build_main_menu_for_user, require_role
from artsecure_bot.i18n import tr, variants
from artsecure_bot.keyboards import art_kind_keyboard, flow_menu, relay_menu
from artsecure_bot.models import ArtAsset, ArtKind, OrderStatus, UserRole
from artsecure_bot.services.repository import get_order_by_id, get_user_language
from artsecure_bot.services.watermark import add_text_watermark
from artsecure_bot.states import RelayState, SendArtState

router = Router()


def _relay_menu_for_artist(language: str, status: OrderStatus):
    can_send_art = status in {
        OrderStatus.IN_PROGRESS,
        OrderStatus.PREVIEW_SENT,
        OrderStatus.PAID_ESCROW,
        OrderStatus.FINAL_REVIEW,
    }
    can_mark_done = status in {OrderStatus.PAID_ESCROW, OrderStatus.FINAL_REVIEW}
    return relay_menu(language=language, can_send_art=can_send_art, can_mark_done=can_mark_done)


@router.message(Command("send_art"))
@router.message(F.text.in_(variants("btn_send_art")))
async def send_art_start(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return

    current_state = await state.get_state()
    if current_state == RelayState.waiting_message.state:
        data = await state.get_data()
        order_id = data.get("order_id")
        async with session_scope() as session:
            artist = await require_role(message, session, UserRole.ARTIST)
            if artist is None:
                return
            lang = await get_user_language(session, artist.tg_id)
            if not isinstance(order_id, int):
                await message.answer(tr("relay_session_expired", lang))
                await state.clear()
                return
            order = await get_order_by_id(session, order_id)
            if order is None:
                await message.answer(tr("order_not_found", lang))
                await state.clear()
                return
            if order.artist_id != artist.id:
                await message.answer(tr("send_art_order_not_yours", lang))
                return
            if order.status in {OrderStatus.CANCELLED, OrderStatus.COMPLETED}:
                menu = await build_main_menu_for_user(session, artist)
                await message.answer(tr("relay_order_closed", lang), reply_markup=menu)
                await state.clear()
                return

        await state.set_state(SendArtState.waiting_kind)
        await state.update_data(order_id=order_id, from_relay=True)
        await message.answer(tr("send_art_choose_kind", lang), reply_markup=art_kind_keyboard(lang))
        return

    async with session_scope() as session:
        artist = await require_role(message, session, UserRole.ARTIST)
        if artist is None:
            return
        lang = await get_user_language(session, artist.tg_id)

    await state.clear()
    await state.set_state(SendArtState.waiting_order_id)
    await message.answer(tr("send_art_ask_order", lang), reply_markup=flow_menu(lang))


@router.message(SendArtState.waiting_order_id)
async def send_art_order_id(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    raw = (message.text or "").strip()
    async with session_scope() as session:
        lang = await get_user_language(session, message.from_user.id)
    if not raw.isdigit():
        await message.answer(tr("order_id_must_be_number", lang))
        return

    await state.update_data(order_id=int(raw))
    await state.set_state(SendArtState.waiting_kind)
    await message.answer(tr("send_art_choose_kind", lang), reply_markup=art_kind_keyboard(lang))


@router.callback_query(F.data.startswith("art_kind:"), SendArtState.waiting_kind)
async def send_art_kind(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data is None or callback.message is None or callback.from_user is None:
        return

    async with session_scope() as session:
        lang = await get_user_language(session, callback.from_user.id)

    _, kind_value = callback.data.split(":", maxsplit=1)
    if kind_value not in {"preview", "direct"}:
        await callback.answer(tr("send_art_unknown_kind", lang), show_alert=True)
        return

    await state.update_data(kind=kind_value)
    await state.set_state(SendArtState.waiting_media)
    await callback.message.answer(tr("send_art_upload_image", lang))
    await callback.answer()


async def _download_media(bot: Bot, photo: PhotoSize | None, document: Document | None) -> tuple[str, bytes] | None:
    if photo is not None:
        file_id = photo.file_id
    elif document is not None:
        mime = (document.mime_type or "").lower()
        if not mime.startswith("image/"):
            return None
        file_id = document.file_id
    else:
        return None

    file = await bot.get_file(file_id)
    destination = io.BytesIO()
    await bot.download_file(file.file_path, destination=destination)
    return file_id, destination.getvalue()


@router.message(SendArtState.waiting_media)
async def send_art_media(message: Message, bot: Bot, state: FSMContext) -> None:
    if message.from_user is None:
        return

    data = await state.get_data()
    order_id = data.get("order_id")
    kind_value = data.get("kind")
    from_relay = bool(data.get("from_relay"))

    async with session_scope() as session:
        lang = await get_user_language(session, message.from_user.id)
        if not isinstance(order_id, int) or kind_value not in {"preview", "direct"}:
            await message.answer(tr("send_art_session_expired", lang))
            await state.clear()
            return

        media = await _download_media(bot, message.photo[-1] if message.photo else None, message.document)
        if media is None:
            await message.answer(tr("send_art_need_image", lang))
            return
        original_file_id, image_bytes = media

        artist = await require_role(message, session, UserRole.ARTIST)
        if artist is None:
            await state.clear()
            return
        menu = await build_main_menu_for_user(session, artist)

        order = await get_order_by_id(session, order_id)
        if order is None:
            await message.answer(tr("order_not_found", lang))
            return

        if order.artist_id != artist.id:
            await message.answer(tr("send_art_order_not_yours", lang))
            return

        if kind_value == "direct" and order.status not in {
            OrderStatus.IN_PROGRESS,
            OrderStatus.PREVIEW_SENT,
            OrderStatus.PAID_ESCROW,
            OrderStatus.FINAL_REVIEW,
        }:
            await message.answer(tr("send_art_direct_not_available", lang))
            return

        customer_tg = order.customer.tg_id
        customer_lang = await get_user_language(session, customer_tg)
        customer_ref = f"@{order.customer.username}" if order.customer.username else str(order.customer.tg_id)
        watermark_file_id = None

        if kind_value == "direct":
            watermarked = add_text_watermark(image_bytes, order_id=order.id, artist_nick=artist.nickname)
            sent = await bot.send_photo(
                chat_id=artist.tg_id,
                photo=BufferedInputFile(watermarked, filename=f"order_{order.id}_direct.jpg"),
                caption=tr("send_art_direct_caption", lang, order_id=order.id),
                protect_content=True,
            )
            watermark_file_id = sent.photo[-1].file_id if sent.photo else None
        else:
            watermarked = add_text_watermark(image_bytes, order_id=order.id, artist_nick=artist.nickname)
            sent = await bot.send_photo(
                chat_id=customer_tg,
                photo=BufferedInputFile(
                    watermarked,
                    filename=f"order_{order.id}_preview.jpg",
                ),
                caption=tr(
                    "send_art_preview_caption",
                    customer_lang,
                    order_id=order.id,
                ),
                protect_content=True,
            )
            watermark_file_id = sent.photo[-1].file_id if sent.photo else None
            # Do not downgrade paid/final/disputed orders back to PREVIEW_SENT.
            if order.status == OrderStatus.IN_PROGRESS:
                order.status = OrderStatus.PREVIEW_SENT

        kind_db = ArtKind.PREVIEW
        asset = ArtAsset(
            order_id=order.id,
            sender_id=artist.id,
            kind=kind_db,
            original_file_id=original_file_id,
            watermarked_file_id=watermark_file_id,
        )
        session.add(asset)

    if from_relay:
        await state.set_state(RelayState.waiting_message)
        await state.update_data(order_id=order_id)
        relay_kb = _relay_menu_for_artist(lang, order.status)
        if kind_value == "preview":
            await message.answer(tr("send_art_preview_done", lang), reply_markup=relay_kb)
            try:
                await bot.send_message(
                    customer_tg,
                    tr("send_art_preview_notify_customer", customer_lang, order_id=order_id),
                    protect_content=True,
                )
            except Exception:
                pass
        else:
            await message.answer(
                tr("send_art_direct_done", lang, customer_ref=customer_ref),
                reply_markup=relay_kb,
            )
        return

    await state.clear()
    if kind_value == "preview":
        await message.answer(tr("send_art_preview_done", lang), reply_markup=menu)
        try:
            await bot.send_message(
                customer_tg,
                tr("send_art_preview_notify_customer", customer_lang, order_id=order_id),
                protect_content=True,
            )
        except Exception:
            pass
    else:
        await message.answer(
            tr("send_art_direct_done", lang, customer_ref=customer_ref),
            reply_markup=menu,
        )
