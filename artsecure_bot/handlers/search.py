from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from artsecure_bot.db import session_scope
from artsecure_bot.handlers.utils import build_main_menu_for_user, require_registered_user
from artsecure_bot.i18n import tr, variants
from artsecure_bot.keyboards import flow_menu
from artsecure_bot.services.repository import get_user_language, search_artists
from artsecure_bot.states import SearchState

router = Router()


async def _run_search(message: Message, query: str) -> None:
    if message.from_user is None:
        return

    async with session_scope() as session:
        user = await require_registered_user(message, session)
        if user is None:
            return

        lang = await get_user_language(session, user.tg_id)
        artists = await search_artists(session, query)
        menu = await build_main_menu_for_user(session, user)

    if not artists:
        await message.answer(tr("search_no_results", lang), reply_markup=menu)
        return

    lines = [tr("search_results_title", lang)]
    for artist in artists:
        username = f"@{artist.username}" if artist.username else tr("no_username", lang)
        lines.append(
            tr(
                "search_item",
                lang,
                nickname=artist.nickname,
                username=username,
                tg_id=artist.tg_id,
                contact=artist.contact,
            )
        )

    await message.answer("\n".join(lines), reply_markup=menu)


@router.message(Command("search"))
@router.message(F.text.in_(variants("btn_search")))
async def search_command(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    async with session_scope() as session:
        lang = await get_user_language(session, message.from_user.id)

    parts = (message.text or "").split(maxsplit=1)
    query = parts[1].strip() if len(parts) == 2 else ""

    if len(query) < 2:
        await state.clear()
        await state.set_state(SearchState.waiting_query)
        await message.answer(tr("search_ask_query", lang), reply_markup=flow_menu(lang))
        return

    await state.clear()
    await _run_search(message, query)


@router.message(SearchState.waiting_query)
async def search_query_input(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    async with session_scope() as session:
        lang = await get_user_language(session, message.from_user.id)
    query = (message.text or "").strip()
    if len(query) < 2:
        await message.answer(tr("search_query_short", lang), reply_markup=flow_menu(lang))
        return

    await state.clear()
    await _run_search(message, query)
