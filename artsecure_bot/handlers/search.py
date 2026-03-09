from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from artsecure_bot.db import session_scope
from artsecure_bot.handlers.utils import require_registered_user
from artsecure_bot.services.repository import search_artists

router = Router()


@router.message(Command("search"))
async def search_command(message: Message, state: FSMContext) -> None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) == 2:
        query = parts[1].strip()
    else:
        query = ""

    if len(query) < 2:
        await message.answer("Введите запрос: /search <ник/username/контакт>")
        return

    async with session_scope() as session:
        user = await require_registered_user(message, session)
        if user is None:
            return

        artists = await search_artists(session, query)

    if not artists:
        await message.answer("Исполнители не найдены.")
        return

    lines = ["Найденные исполнители:"]
    for artist in artists:
        username = f"@{artist.username}" if artist.username else "без username"
        lines.append(
            f"- {artist.nickname} | {username} | TG ID: {artist.tg_id} | контакт: {artist.contact}"
        )

    await message.answer("\n".join(lines))
