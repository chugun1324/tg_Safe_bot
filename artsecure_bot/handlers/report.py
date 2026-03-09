from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from artsecure_bot.db import session_scope
from artsecure_bot.handlers.utils import require_registered_user
from artsecure_bot.services.repository import create_report, get_user_by_tg_id
from artsecure_bot.states import ReportState

router = Router()


@router.message(Command("report"))
async def report_start(message: Message, state: FSMContext) -> None:
    async with session_scope() as session:
        user = await require_registered_user(message, session)
    if user is None:
        return

    await state.clear()
    await state.set_state(ReportState.waiting_target_tg_id)
    await message.answer("Введите TG ID пользователя, на которого хотите пожаловаться:")


@router.message(ReportState.waiting_target_tg_id)
async def report_target(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("TG ID должен быть числом.")
        return

    await state.update_data(target_tg_id=int(raw))
    await state.set_state(ReportState.waiting_order_id)
    await message.answer("Укажите ID заказа (или 0, если жалоба не связана с заказом):")


@router.message(ReportState.waiting_order_id)
async def report_order_id(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("Нужен числовой ID заказа или 0.")
        return

    order_id = int(raw)
    await state.update_data(order_id=order_id if order_id > 0 else None)
    await state.set_state(ReportState.waiting_reason)
    await message.answer("Опишите причину жалобы:")


@router.message(ReportState.waiting_reason)
async def report_reason(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return

    reason = (message.text or "").strip()
    if len(reason) < 8:
        await message.answer("Опишите проблему подробнее (минимум 8 символов).")
        return

    data = await state.get_data()
    target_tg_id = data.get("target_tg_id")
    order_id = data.get("order_id")

    async with session_scope() as session:
        reporter = await get_user_by_tg_id(session, message.from_user.id)
        target = await get_user_by_tg_id(session, int(target_tg_id)) if target_tg_id else None

        if reporter is None:
            await message.answer("Сначала зарегистрируйтесь через /start")
            await state.clear()
            return

        if target is None:
            await message.answer("Пользователь с таким TG ID не найден в системе.")
            return

        report = await create_report(
            session=session,
            reporter_id=reporter.id,
            target_user_id=target.id,
            order_id=order_id,
            reason=reason,
        )

    await state.clear()
    await message.answer(
        f"Жалоба #{report.id} создана. Администратор рассмотрит ее в течение 7 дней."
    )
