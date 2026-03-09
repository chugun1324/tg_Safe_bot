from __future__ import annotations

from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from artsecure_bot.models import User, UserRole
from artsecure_bot.services.repository import get_user_by_tg_id


async def require_registered_user(message: Message, session: AsyncSession) -> User | None:
    if message.from_user is None:
        return None

    user = await get_user_by_tg_id(session, message.from_user.id)
    if user is None:
        await message.answer("Сначала зарегистрируйтесь через /start")
        return None

    if user.is_banned:
        await message.answer("Ваш аккаунт ограничен администратором.")
        return None

    return user


async def require_role(message: Message, session: AsyncSession, role: UserRole) -> User | None:
    user = await require_registered_user(message, session)
    if user is None:
        return None
    if user.role != role:
        await message.answer("Эта команда доступна для другой роли пользователя.")
        return None
    return user
