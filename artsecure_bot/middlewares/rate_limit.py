from __future__ import annotations

from collections.abc import Awaitable, Callable
from time import monotonic
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject


class RateLimitMiddleware(BaseMiddleware):
    def __init__(self, min_interval_seconds: float) -> None:
        self.min_interval = min_interval_seconds
        self._last_seen: dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user

        if user is None:
            return await handler(event, data)

        now = monotonic()
        last = self._last_seen.get(user.id, 0.0)
        self._last_seen[user.id] = now
        if now - last < self.min_interval:
            if isinstance(event, Message):
                await event.answer("Слишком часто. Подождите секунду и повторите.")
            elif isinstance(event, CallbackQuery):
                await event.answer("Слишком часто", show_alert=False)
            return None

        return await handler(event, data)
