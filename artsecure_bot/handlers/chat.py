from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from artsecure_bot.db import session_scope
from artsecure_bot.handlers.utils import require_registered_user
from artsecure_bot.models import OrderStatus
from artsecure_bot.services.repository import get_order_by_id
from artsecure_bot.states import RelayState

router = Router()


def _extract_order_id(message: Message) -> int | None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].isdigit():
        return None
    return int(parts[1])


@router.message(Command("relay"))
async def relay_start(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return

    order_id = _extract_order_id(message)
    if order_id is None:
        await message.answer("Использование: /relay <order_id>")
        return

    async with session_scope() as session:
        user = await require_registered_user(message, session)
        if user is None:
            return

        order = await get_order_by_id(session, order_id)
        if order is None:
            await message.answer("Заказ не найден.")
            return

        if user.id not in {order.customer_id, order.artist_id}:
            await message.answer("Вы не участник этого заказа.")
            return

        if order.status in {OrderStatus.CANCELLED, OrderStatus.COMPLETED}:
            await message.answer("Этот заказ уже закрыт.")
            return

    await state.clear()
    await state.set_state(RelayState.waiting_message)
    await state.update_data(order_id=order_id)
    await message.answer(
        (
            f"Relay-чат для заказа #{order_id} активирован.\n"
            "Отправляйте текстовые сообщения, бот перешлет их второй стороне.\n"
            "Выход: /leave_relay"
        )
    )


@router.message(Command("leave_relay"))
async def relay_leave(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Relay-чат выключен.")


@router.message(RelayState.waiting_message)
async def relay_message(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return

    text = (message.text or "").strip()
    if not text:
        await message.answer("Отправьте текстовое сообщение.")
        return

    if text.startswith("/"):
        await message.answer("Для выхода используйте /leave_relay")
        return

    data = await state.get_data()
    order_id = data.get("order_id")
    if not isinstance(order_id, int):
        await message.answer("Сессия relay устарела. Используйте /relay <order_id>.")
        await state.clear()
        return

    async with session_scope() as session:
        user = await require_registered_user(message, session)
        if user is None:
            return

        order = await get_order_by_id(session, order_id)
        if order is None:
            await message.answer("Заказ не найден.")
            await state.clear()
            return

        if user.id == order.customer_id:
            target_tg_id = order.artist.tg_id
            sender_role = "Заказчик"
        elif user.id == order.artist_id:
            target_tg_id = order.customer.tg_id
            sender_role = "Исполнитель"
        else:
            await message.answer("Вы больше не участник этого заказа.")
            await state.clear()
            return

    await message.bot.send_message(
        target_tg_id,
        (
            f"[Relay заказ #{order_id}] {sender_role} {message.from_user.full_name}:\n"
            f"{text}"
        ),
        protect_content=True,
    )
    await message.answer("Сообщение отправлено.")
