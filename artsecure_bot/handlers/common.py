from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from artsecure_bot.config import Settings
from artsecure_bot.db import session_scope
from artsecure_bot.handlers.utils import build_main_menu_for_user
from artsecure_bot.i18n import DEFAULT_LANGUAGE, normalize_language, tr, variants
from artsecure_bot.keyboards import flow_menu, language_keyboard, role_keyboard
from artsecure_bot.models import UserRole
from artsecure_bot.services.repository import (
    get_user_by_tg_id,
    get_user_language,
    set_user_language,
    upsert_user,
)
from artsecure_bot.states import RegistrationState

router = Router()
FLOW_TEXT_VARIANTS = (
    variants("btn_help")
    | variants("btn_rules")
    | variants("btn_cancel")
    | variants("btn_exit")
    | variants("btn_language")
)


def _role_label(role: UserRole, lang: str) -> str:
    if role == UserRole.CUSTOMER:
        return tr("role_customer", lang)
    if role == UserRole.ARTIST:
        return tr("role_artist", lang)
    return role.value


async def _lang_by_tg_id(tg_id: int | None) -> str:
    if tg_id is None:
        return DEFAULT_LANGUAGE
    async with session_scope() as session:
        return await get_user_language(session, tg_id)


async def _main_menu_for_tg_id(tg_id: int):
    async with session_scope() as session:
        user = await get_user_by_tg_id(session, tg_id)
        if user is None:
            return ReplyKeyboardRemove()
        return await build_main_menu_for_user(session, user)


@router.message(CommandStart())
async def start_command(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return

    async with session_scope() as session:
        lang = await get_user_language(session, message.from_user.id)
        user = await get_user_by_tg_id(session, message.from_user.id)

    if user is None:
        await state.clear()
        await state.set_state(RegistrationState.waiting_role)
        await message.answer(tr("start_welcome", lang), reply_markup=ReplyKeyboardRemove())
        await message.answer(tr("start_choose_role", lang), reply_markup=role_keyboard(lang))
        return

    await message.answer(
        tr("start_registered", lang, role=_role_label(user.role, lang)),
        reply_markup=await _main_menu_for_tg_id(message.from_user.id),
    )


@router.callback_query(F.data.startswith("reg_role:"))
async def choose_role(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data is None or callback.message is None:
        return

    lang = await _lang_by_tg_id(callback.from_user.id if callback.from_user else None)
    raw_role = callback.data.split(":", maxsplit=1)[1]
    if raw_role not in {"customer", "artist"}:
        await callback.answer(tr("invalid_role", lang), show_alert=True)
        return

    role = UserRole.CUSTOMER if raw_role == "customer" else UserRole.ARTIST
    await state.update_data(role=role.value)
    await state.set_state(RegistrationState.waiting_nickname)
    await callback.message.answer(tr("ask_nickname", lang), reply_markup=flow_menu(lang))
    await callback.answer()


@router.message(
    RegistrationState.waiting_nickname,
    ~F.text.startswith("/"),
    ~F.text.in_(FLOW_TEXT_VARIANTS),
)
async def registration_nickname(message: Message, state: FSMContext) -> None:
    lang = await _lang_by_tg_id(message.from_user.id if message.from_user else None)
    nickname = (message.text or "").strip()
    if len(nickname) < 2:
        await message.answer(tr("nick_too_short", lang))
        return

    await state.update_data(nickname=nickname)
    await state.set_state(RegistrationState.waiting_contact)
    await message.answer(tr("ask_contact", lang), reply_markup=flow_menu(lang))


@router.message(
    RegistrationState.waiting_contact,
    ~F.text.startswith("/"),
    ~F.text.in_(FLOW_TEXT_VARIANTS),
)
async def registration_contact(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return

    lang = await _lang_by_tg_id(message.from_user.id)
    contact = (message.text or "").strip()
    if len(contact) < 3:
        await message.answer(tr("contact_too_short", lang))
        return

    data = await state.get_data()
    role_value = data.get("role")
    nickname = data.get("nickname")

    if role_value not in {"customer", "artist"} or not nickname:
        await state.clear()
        await message.answer(tr("registration_expired", lang))
        return

    role = UserRole.CUSTOMER if role_value == "customer" else UserRole.ARTIST

    async with session_scope() as session:
        user = await upsert_user(
            session=session,
            tg_id=message.from_user.id,
            username=message.from_user.username,
            role=role,
            nickname=nickname,
            contact=contact,
        )

    await state.clear()
    await message.answer(
        tr("registration_done", lang, role=_role_label(user.role, lang)),
        reply_markup=await _main_menu_for_tg_id(message.from_user.id),
    )


@router.message(Command("langue"))
@router.message(F.text.in_(variants("btn_language")))
async def language_command(message: Message) -> None:
    lang = await _lang_by_tg_id(message.from_user.id if message.from_user else None)
    await message.answer(tr("language_choose", lang), reply_markup=language_keyboard())


@router.callback_query(F.data.startswith("set_lang:"))
async def set_language_callback(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data is None or callback.from_user is None or callback.message is None:
        return

    requested = callback.data.split(":", maxsplit=1)[1]
    lang = normalize_language(requested)

    async with session_scope() as session:
        await set_user_language(session, callback.from_user.id, lang)
        user = await get_user_by_tg_id(session, callback.from_user.id)

    await callback.answer()
    await callback.message.answer(tr("language_saved", lang, language_name=tr(f"lang_{lang}", lang)))

    current_state = await state.get_state()
    if current_state == RegistrationState.waiting_role.state or user is None:
        await callback.message.answer(tr("start_choose_role", lang), reply_markup=role_keyboard(lang))
        return

    await callback.message.answer(
        tr("start_registered", lang, role=_role_label(user.role, lang)),
        reply_markup=await _main_menu_for_tg_id(callback.from_user.id),
    )


@router.message(Command("help"))
@router.message(F.text.in_(variants("btn_help")))
async def help_command(message: Message, settings: Settings) -> None:
    lang = await _lang_by_tg_id(message.from_user.id if message.from_user else None)
    text = tr(
        "help_text",
        lang,
        btn_create_order=tr("btn_create_order", lang),
        btn_my_orders=tr("btn_my_orders", lang),
        btn_send_art=tr("btn_send_art", lang),
        btn_search=tr("btn_search", lang),
        btn_report=tr("btn_report", lang),
        support_chat_url=settings.support_chat_url,
    )
    await message.answer(text)


@router.message(Command("rules"))
@router.message(F.text.in_(variants("btn_rules")))
async def rules_command(message: Message, settings: Settings) -> None:
    lang = await _lang_by_tg_id(message.from_user.id if message.from_user else None)
    await message.answer(tr("rules_text", lang, news_channel=settings.news_channel))


@router.message(Command("cancel"))
@router.message(F.text.in_(variants("btn_cancel")))
async def cancel_command(message: Message, state: FSMContext) -> None:
    await state.clear()
    lang = await _lang_by_tg_id(message.from_user.id if message.from_user else None)
    if message.from_user is None:
        await message.answer(tr("scenario_cancelled", lang), reply_markup=ReplyKeyboardRemove())
        return
    await message.answer(
        tr("scenario_cancelled", lang),
        reply_markup=await _main_menu_for_tg_id(message.from_user.id),
    )


@router.message(Command("exit"))
@router.message(F.text.in_(variants("btn_exit")))
async def exit_to_role_selection(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(RegistrationState.waiting_role)
    lang = await _lang_by_tg_id(message.from_user.id if message.from_user else None)
    await message.answer(tr("exit_role_selecting", lang), reply_markup=ReplyKeyboardRemove())
    await message.answer(tr("exit_role_selected", lang), reply_markup=role_keyboard(lang))
