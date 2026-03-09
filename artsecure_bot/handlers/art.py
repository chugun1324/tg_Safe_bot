from __future__ import annotations

import io

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Document, Message, PhotoSize

from artsecure_bot.db import session_scope
from artsecure_bot.handlers.utils import require_role
from artsecure_bot.keyboards import art_kind_keyboard
from artsecure_bot.models import ArtAsset, ArtKind, OrderStatus, UserRole
from artsecure_bot.services.repository import get_order_by_id
from artsecure_bot.services.watermark import add_text_watermark
from artsecure_bot.states import SendArtState

router = Router()


@router.message(Command("send_art"))
async def send_art_start(message: Message, state: FSMContext) -> None:
    async with session_scope() as session:
        artist = await require_role(message, session, UserRole.ARTIST)
    if artist is None:
        return

    await state.clear()
    await state.set_state(SendArtState.waiting_order_id)
    await message.answer("Введите ID заказа, по которому отправляете файл:")


@router.message(SendArtState.waiting_order_id)
async def send_art_order_id(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("ID заказа должен быть числом.")
        return

    await state.update_data(order_id=int(raw))
    await state.set_state(SendArtState.waiting_kind)
    await message.answer("Выберите тип отправки:", reply_markup=art_kind_keyboard())


@router.callback_query(F.data.startswith("art_kind:"), SendArtState.waiting_kind)
async def send_art_kind(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data is None or callback.message is None:
        return

    _, kind_value = callback.data.split(":", maxsplit=1)
    if kind_value not in {"preview", "final"}:
        await callback.answer("Неизвестный тип", show_alert=True)
        return

    await state.update_data(kind=kind_value)
    await state.set_state(SendArtState.waiting_media)
    await callback.message.answer("Отправьте изображение (фото или документ-изображение).")
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

    if not isinstance(order_id, int) or kind_value not in {"preview", "final"}:
        await message.answer("Сессия отправки устарела. Повторите /send_art")
        await state.clear()
        return

    kind = ArtKind.PREVIEW if kind_value == "preview" else ArtKind.FINAL

    media = await _download_media(bot, message.photo[-1] if message.photo else None, message.document)
    if media is None:
        await message.answer("Нужна картинка: отправьте фото или документ-изображение.")
        return

    original_file_id, image_bytes = media

    async with session_scope() as session:
        artist = await require_role(message, session, UserRole.ARTIST)
        if artist is None:
            await state.clear()
            return

        order = await get_order_by_id(session, order_id)
        if order is None:
            await message.answer("Заказ не найден.")
            return

        if order.artist_id != artist.id:
            await message.answer("Этот заказ не назначен на вас.")
            return

        if kind == ArtKind.FINAL and order.status not in {OrderStatus.PAID_ESCROW, OrderStatus.FINAL_REVIEW}:
            await message.answer(
                "Финал можно отправить только после escrow оплаты заказчиком (/pay)."
            )
            return

        watermark_file_id = None
        if kind == ArtKind.PREVIEW:
            watermarked = add_text_watermark(image_bytes, order_id=order.id, artist_nick=artist.nickname)
            sent = await bot.send_photo(
                chat_id=order.customer.tg_id,
                photo=BufferedInputFile(watermarked, filename=f"order_{order.id}_preview.jpg"),
                caption=(
                    f"Предпросмотр по заказу #{order.id}.\n"
                    "Файл защищен и предназначен только для проверки до оплаты."
                ),
                protect_content=True,
            )
            order.status = OrderStatus.PREVIEW_SENT
            watermark_file_id = sent.photo[-1].file_id if sent.photo else None
        else:
            sent = await bot.send_photo(
                chat_id=order.customer.tg_id,
                photo=BufferedInputFile(image_bytes, filename=f"order_{order.id}_final.jpg"),
                caption=(
                    f"Финальный файл по заказу #{order.id}.\n"
                    "Рекомендуется дополнительно отправить оригинал в приватном чате как disappearing media (1:1)."
                ),
                protect_content=True,
            )
            order.status = OrderStatus.FINAL_REVIEW
            watermark_file_id = sent.photo[-1].file_id if sent.photo else None

        asset = ArtAsset(
            order_id=order.id,
            sender_id=artist.id,
            kind=kind,
            original_file_id=original_file_id,
            watermarked_file_id=watermark_file_id,
        )
        session.add(asset)
        customer_tg = order.customer.tg_id

    await state.clear()
    if kind == ArtKind.PREVIEW:
        await message.answer(
            (
                "Предпросмотр отправлен заказчику.\n"
                "Дальше: заказчик подтверждает оплату escrow через /pay <order_id>."
            )
        )
        await bot.send_message(
            customer_tg,
            (
                f"Заказ #{order_id}: после проверки предпросмотра используйте /pay {order_id}, "
                "чтобы перейти к финальной передаче."
            ),
            protect_content=True,
        )
    else:
        await message.answer(
            (
                "Финал отправлен заказчику.\n"
                f"Ожидайте релиз средств командой /release {order_id} от заказчика."
            )
        )
