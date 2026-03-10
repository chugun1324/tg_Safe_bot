from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, Message

from artsecure_bot.config import Settings
from artsecure_bot.db import session_scope
from artsecure_bot.handlers.utils import require_registered_user
from artsecure_bot.i18n import tr
from artsecure_bot.services.nda import build_nda_pdf
from artsecure_bot.services.repository import get_order_by_id, get_user_language

router = Router()


def _extract_order_id(message: Message) -> int | None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].isdigit():
        return None
    return int(parts[1])


@router.message(Command("nda"))
async def nda_command(message: Message, settings: Settings) -> None:
    if message.from_user is None:
        return

    async with session_scope() as session:
        lang = await get_user_language(session, message.from_user.id)
        order_id = _extract_order_id(message)
        if order_id is None:
            await message.answer(tr("usage_nda", lang))
            return

        user = await require_registered_user(message, session)
        if user is None:
            return

        order = await get_order_by_id(session, order_id)
        if order is None:
            await message.answer(tr("order_not_found", lang))
            return

        from_admin = message.from_user.id in settings.admin_ids
        if user.id not in {order.customer_id, order.artist_id} and not from_admin:
            await message.answer(tr("nda_not_available", lang))
            return

        pdf_bytes = build_nda_pdf(
            order_id=order.id,
            customer_name=order.customer.nickname,
            artist_name=order.artist.nickname,
            work_title=order.title,
            price_rub=order.price_rub,
        )

    await message.answer_document(
        BufferedInputFile(pdf_bytes, filename=f"nda_order_{order_id}.pdf"),
        caption=tr("nda_generated", lang),
        protect_content=True,
    )
