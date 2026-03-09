from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from artsecure_bot.config import Settings
from artsecure_bot.db import session_scope
from artsecure_bot.keyboards import main_menu, role_keyboard
from artsecure_bot.models import UserRole
from artsecure_bot.services.repository import get_user_by_tg_id, upsert_user
from artsecure_bot.states import RegistrationState

router = Router()


@router.message(CommandStart())
async def start_command(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return

    async with session_scope() as session:
        user = await get_user_by_tg_id(session, message.from_user.id)

    if user is None:
        await state.clear()
        await state.set_state(RegistrationState.waiting_role)
        await message.answer(
            "Добро пожаловать в ArtSecure. Выберите вашу роль:",
            reply_markup=role_keyboard(),
        )
        return

    await message.answer(
        (
            f"Вы уже зарегистрированы как {user.role.value}.\n"
            "Основные команды: /create, /my_orders, /send_art, /report, /search"
        ),
        reply_markup=main_menu(user.role),
    )


@router.callback_query(F.data.startswith("reg_role:"))
async def choose_role(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data is None or callback.message is None:
        return

    raw_role = callback.data.split(":", maxsplit=1)[1]
    if raw_role not in {"customer", "artist"}:
        await callback.answer("Неверная роль", show_alert=True)
        return

    role = UserRole.CUSTOMER if raw_role == "customer" else UserRole.ARTIST
    await state.update_data(role=role.value)
    await state.set_state(RegistrationState.waiting_nickname)
    await callback.message.answer("Введите ваш ник (псевдоним):")
    await callback.answer()


@router.message(RegistrationState.waiting_nickname)
async def registration_nickname(message: Message, state: FSMContext) -> None:
    nickname = (message.text or "").strip()
    if len(nickname) < 2:
        await message.answer("Ник слишком короткий. Минимум 2 символа.")
        return

    await state.update_data(nickname=nickname)
    await state.set_state(RegistrationState.waiting_contact)
    await message.answer("Укажите контакт (Telegram @username или другой способ связи):")


@router.message(RegistrationState.waiting_contact)
async def registration_contact(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return

    contact = (message.text or "").strip()
    if len(contact) < 3:
        await message.answer("Контакт слишком короткий.")
        return

    data = await state.get_data()
    role_value = data.get("role")
    nickname = data.get("nickname")

    if role_value not in {"customer", "artist"} or not nickname:
        await state.clear()
        await message.answer("Сессия регистрации устарела. Повторите /start")
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
        (
            f"Регистрация завершена. Роль: {user.role.value}.\n"
            "Доступные команды: /create, /my_orders, /search, /report"
        ),
        reply_markup=main_menu(user.role),
    )


@router.message(Command("help"))
async def help_command(message: Message, settings: Settings) -> None:
    text = (
        "Команды:\n"
        "/start - регистрация\n"
        "/create - создать заказ\n"
        "/my_orders - список заказов\n"
        "/send_art - отправка предпросмотра/финала\n"
        "/search - поиск исполнителя\n"
        "/report - жалоба\n"
        "/relay <id> - защищенный relay-чат по заказу\n"
        "/leave_relay - выйти из relay-чата\n"
        "/pay <id> - имитация escrow оплаты\n"
        "/release <id> - релиз средств исполнителю\n"
        "/dispute <id> - открыть спор\n"
        "/force_close <id> - принудительно закрыть заказ\n"
        "/nda <id> - шаблон NDA в PDF\n"
        f"Поддержка: {settings.support_chat_url}"
    )
    await message.answer(text)


@router.message(Command("rules"))
async def rules_command(message: Message, settings: Settings) -> None:
    text = (
        "Правила ArtSecure:\n"
        "1) Кража ИС запрещена, за повторные жалобы выдается бан.\n"
        "2) Комиссия платформы: 10% (или 0% при премиуме исполнителя).\n"
        "3) Споры рассматриваются админом до 7 дней.\n"
        "4) Protect content и disappearing media снижают риск, но не дают 100% защиты.\n"
        f"5) Новости: {settings.news_channel}"
    )
    await message.answer(text)


@router.message(Command("cancel"))
async def cancel_command(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Текущий сценарий отменен.")
