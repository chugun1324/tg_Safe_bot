from __future__ import annotations

from aiogram import Bot


async def clear_chat_keep_message(
    bot: Bot,
    chat_id: int,
    keep_message_id: int,
    history_window: int = 2000,
) -> None:
    start_id = max(1, keep_message_id - history_window)
    for message_id in range(start_id, keep_message_id):
        try:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception:
            continue
