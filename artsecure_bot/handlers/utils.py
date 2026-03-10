from __future__ import annotations

from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from artsecure_bot.i18n import DEFAULT_LANGUAGE, tr
from artsecure_bot.keyboards import main_menu
from artsecure_bot.models import User, UserRole
from artsecure_bot.services.repository import (
    get_user_by_tg_id,
    has_orders_for_artist,
    has_orders_for_customer,
    has_send_art_available_orders,
    get_user_language,
)


async def require_registered_user(message: Message, session: AsyncSession) -> User | None:
    if message.from_user is None:
        return None

    lang = await get_user_language(session, message.from_user.id)
    user = await get_user_by_tg_id(session, message.from_user.id)
    if user is None:
        await message.answer(tr("err_not_registered", lang))
        return None

    if user.is_banned:
        await message.answer(tr("err_banned", lang))
        return None

    return user


async def require_role(message: Message, session: AsyncSession, role: UserRole) -> User | None:
    user = await require_registered_user(message, session)
    if user is None:
        return None
    if user.role != role:
        lang = await get_user_language(session, user.tg_id)
        await message.answer(tr("err_wrong_role", lang))
        return None
    return user


async def build_main_menu_for_user(session: AsyncSession, user: User):
    language = await get_user_language(session, user.tg_id)
    if user.role == UserRole.CUSTOMER:
        has_orders = await has_orders_for_customer(session, user.id)
        return main_menu(user.role, has_orders=has_orders, can_send_art=False, language=language)
    if user.role == UserRole.ARTIST:
        has_orders = await has_orders_for_artist(session, user.id)
        can_send_art = await has_send_art_available_orders(session, user.id)
        return main_menu(user.role, has_orders=has_orders, can_send_art=can_send_art, language=language)
    return main_menu(user.role, has_orders=False, can_send_art=False, language=language)


async def language_by_tg_id(session: AsyncSession, tg_id: int | None) -> str:
    if tg_id is None:
        return DEFAULT_LANGUAGE
    return await get_user_language(session, tg_id)
