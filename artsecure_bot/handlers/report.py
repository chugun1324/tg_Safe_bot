from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from artsecure_bot.db import session_scope
from artsecure_bot.handlers.utils import build_main_menu_for_user, require_registered_user
from artsecure_bot.i18n import tr, variants
from artsecure_bot.keyboards import flow_menu
from artsecure_bot.services.repository import (
    create_report,
    get_user_by_tg_id,
    get_user_language,
)
from artsecure_bot.states import ReportState

router = Router()


@router.message(Command("report"))
@router.message(F.text.in_(variants("btn_report")))
async def report_start(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    async with session_scope() as session:
        user = await require_registered_user(message, session)
        if user is None:
            return
        lang = await get_user_language(session, user.tg_id)

    await state.clear()
    await state.set_state(ReportState.waiting_target_tg_id)
    await message.answer(tr("report_ask_target", lang), reply_markup=flow_menu(lang))


@router.message(ReportState.waiting_target_tg_id)
async def report_target(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    async with session_scope() as session:
        lang = await get_user_language(session, message.from_user.id)
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer(tr("report_target_id_number", lang))
        return

    await state.update_data(target_tg_id=int(raw))
    await state.set_state(ReportState.waiting_order_id)
    await message.answer(tr("report_ask_order_id", lang), reply_markup=flow_menu(lang))


@router.message(ReportState.waiting_order_id)
async def report_order_id(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    async with session_scope() as session:
        lang = await get_user_language(session, message.from_user.id)
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer(tr("report_order_number_or_zero", lang))
        return

    order_id = int(raw)
    await state.update_data(order_id=order_id if order_id > 0 else None)
    await state.set_state(ReportState.waiting_reason)
    await message.answer(tr("report_ask_reason", lang), reply_markup=flow_menu(lang))


@router.message(ReportState.waiting_reason)
async def report_reason(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return

    reason = (message.text or "").strip()
    async with session_scope() as session:
        lang = await get_user_language(session, message.from_user.id)
    if len(reason) < 8:
        await message.answer(tr("report_reason_short", lang))
        return

    data = await state.get_data()
    target_tg_id = data.get("target_tg_id")
    order_id = data.get("order_id")

    async with session_scope() as session:
        reporter = await get_user_by_tg_id(session, message.from_user.id)
        target = await get_user_by_tg_id(session, int(target_tg_id)) if target_tg_id else None

        if reporter is None:
            await message.answer(tr("err_not_registered", lang))
            await state.clear()
            return

        if target is None:
            await message.answer(tr("report_target_not_found", lang))
            return

        report = await create_report(
            session=session,
            reporter_id=reporter.id,
            target_user_id=target.id,
            order_id=order_id,
            reason=reason,
        )
        menu = await build_main_menu_for_user(session, reporter)

    await state.clear()
    await message.answer(tr("report_created", lang, report_id=report.id), reply_markup=menu)
