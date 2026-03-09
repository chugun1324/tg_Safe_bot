from __future__ import annotations

from aiogram import F, Bot, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from artsecure_bot.config import Settings
from artsecure_bot.db import session_scope
from artsecure_bot.handlers.utils import require_registered_user, require_role
from artsecure_bot.keyboards import order_actions_keyboard, order_decision_keyboard
from artsecure_bot.models import OrderStatus, UserRole
from artsecure_bot.services.order_logic import (
    calculate_commission,
    is_premium_active,
    payout_amount,
    status_label,
)
from artsecure_bot.services.repository import (
    create_order,
    get_order_by_id,
    get_user_by_tg_id,
    list_orders_for_user,
)
from artsecure_bot.states import CreateOrderState

router = Router()


@router.message(Command("create"))
async def create_order_start(message: Message, state: FSMContext) -> None:
    async with session_scope() as session:
        customer = await require_role(message, session, UserRole.CUSTOMER)
    if customer is None:
        return

    await state.clear()
    await state.set_state(CreateOrderState.waiting_artist_tg_id)
    await message.answer("Введите Telegram ID исполнителя (число), которому хотите отправить заявку:")


@router.message(CreateOrderState.waiting_artist_tg_id)
async def create_order_artist_id(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("Нужен числовой Telegram ID исполнителя.")
        return

    artist_tg_id = int(raw)
    async with session_scope() as session:
        artist = await get_user_by_tg_id(session, artist_tg_id)

    if artist is None or artist.role != UserRole.ARTIST:
        await message.answer("Исполнитель не найден или не зарегистрирован в роли исполнителя.")
        return

    await state.update_data(artist_tg_id=artist_tg_id)
    await state.set_state(CreateOrderState.waiting_title)
    await message.answer("Введите название заказа:")


@router.message(CreateOrderState.waiting_title)
async def create_order_title(message: Message, state: FSMContext) -> None:
    title = (message.text or "").strip()
    if len(title) < 3:
        await message.answer("Название слишком короткое.")
        return

    await state.update_data(title=title)
    await state.set_state(CreateOrderState.waiting_details)
    await message.answer("Опишите детали заказа:")


@router.message(CreateOrderState.waiting_details)
async def create_order_details(message: Message, state: FSMContext) -> None:
    details = (message.text or "").strip()
    if len(details) < 5:
        await message.answer("Опишите заказ чуть подробнее (минимум 5 символов).")
        return

    await state.update_data(details=details)
    await state.set_state(CreateOrderState.waiting_price)
    await message.answer("Введите цену в рублях (например 3500):")


@router.message(CreateOrderState.waiting_price)
async def create_order_price(message: Message, bot: Bot, state: FSMContext) -> None:
    if message.from_user is None:
        return

    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("Цена должна быть целым числом в рублях.")
        return

    price = int(raw)
    if price <= 0:
        await message.answer("Цена должна быть больше нуля.")
        return

    data = await state.get_data()
    artist_tg_id = data.get("artist_tg_id")
    title = data.get("title")
    details = data.get("details")

    if not artist_tg_id or not title or not details:
        await message.answer("Сценарий устарел. Начните заново: /create")
        await state.clear()
        return

    async with session_scope() as session:
        customer = await get_user_by_tg_id(session, message.from_user.id)
        artist = await get_user_by_tg_id(session, int(artist_tg_id))
        if customer is None or artist is None:
            await message.answer("Не удалось создать заказ: пользователь не найден.")
            await state.clear()
            return

        if customer.role != UserRole.CUSTOMER:
            await message.answer("Создавать заказ может только заказчик.")
            await state.clear()
            return

        order = await create_order(
            session=session,
            customer_id=customer.id,
            artist_id=artist.id,
            title=title,
            details=details,
            price_rub=price,
        )

    await state.clear()
    await message.answer(
        (
            f"Заявка #{order.id} создана и отправлена исполнителю.\n"
            f"Название: {title}\nЦена: {price} RUB\n"
            "Ожидайте принятия заявки."
        )
    )

    try:
        await bot.send_message(
            artist_tg_id,
            (
                f"Новая заявка #{order.id}\n"
                f"От: {message.from_user.full_name} (@{message.from_user.username or 'без username'})\n"
                f"Название: {title}\n"
                f"Детали: {details}\n"
                f"Цена: {price} RUB"
            ),
            reply_markup=order_decision_keyboard(order.id),
            protect_content=True,
        )
    except Exception:
        await message.answer(
            "Не удалось отправить заявку исполнителю в ЛС. Убедитесь, что он начал диалог с ботом через /start."
        )


@router.callback_query(F.data.startswith("order_decision:"))
async def order_decision(callback: CallbackQuery, bot: Bot) -> None:
    if callback.from_user is None or callback.data is None:
        return

    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("Неверный формат", show_alert=True)
        return

    _, order_id_raw, action = parts
    if not order_id_raw.isdigit() or action not in {"accept", "reject"}:
        await callback.answer("Неверные данные", show_alert=True)
        return

    order_id = int(order_id_raw)

    async with session_scope() as session:
        order = await get_order_by_id(session, order_id)
        artist = await get_user_by_tg_id(session, callback.from_user.id)
        if order is None or artist is None:
            await callback.answer("Заказ не найден", show_alert=True)
            return

        if order.artist_id != artist.id:
            await callback.answer("Это не ваш заказ", show_alert=True)
            return

        if order.status != OrderStatus.PENDING_ARTIST:
            await callback.answer("Заказ уже обработан")
            return

        if action == "accept":
            order.status = OrderStatus.IN_PROGRESS
            customer_tg = order.customer.tg_id
            artist_tg = order.artist.tg_id
            await callback.answer("Заявка принята")
            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.message.answer("Заявка принята. Можете обсудить детали и ждать оплату escrow.")
        else:
            order.status = OrderStatus.CANCELLED
            customer_tg = order.customer.tg_id
            artist_tg = order.artist.tg_id
            await callback.answer("Заявка отклонена")
            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.message.answer("Заявка отклонена.")

    if action == "accept":
        await bot.send_message(customer_tg, f"Исполнитель принял заявку #{order_id}.", protect_content=True)
        await bot.send_message(
            artist_tg,
            (
                f"Заказ #{order_id} переведен в работу.\n"
                "Используйте /relay <order_id> для безопасной переписки в рамках заказа."
            ),
            protect_content=True,
        )
    else:
        await bot.send_message(customer_tg, f"Исполнитель отклонил заявку #{order_id}.", protect_content=True)


@router.message(Command("my_orders"))
async def my_orders(message: Message) -> None:
    async with session_scope() as session:
        user = await require_registered_user(message, session)
        if user is None:
            return

        orders = await list_orders_for_user(session, user)

    if not orders:
        await message.answer("У вас пока нет заказов.")
        return

    for order in orders:
        text = (
            f"Заказ #{order.id}\n"
            f"Статус: {status_label(order.status)}\n"
            f"Название: {order.title}\n"
            f"Цена: {order.price_rub} RUB\n"
            f"Заказчик: {order.customer.nickname} ({order.customer.tg_id})\n"
            f"Исполнитель: {order.artist.nickname} ({order.artist.tg_id})"
        )
        markup = order_actions_keyboard(order.id) if user.role == UserRole.CUSTOMER else None
        await message.answer(text, reply_markup=markup)


def _extract_order_id(message: Message) -> int | None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].isdigit():
        return None
    return int(parts[1])


@router.message(Command("pay"))
async def pay_order(message: Message, bot: Bot) -> None:
    order_id = _extract_order_id(message)
    if order_id is None:
        await message.answer("Использование: /pay <order_id>")
        return

    async with session_scope() as session:
        customer = await require_role(message, session, UserRole.CUSTOMER)
        if customer is None:
            return

        order = await get_order_by_id(session, order_id)
        if order is None:
            await message.answer("Заказ не найден.")
            return

        if order.customer_id != customer.id:
            await message.answer("Это не ваш заказ.")
            return

        if order.status not in {OrderStatus.IN_PROGRESS, OrderStatus.PREVIEW_SENT}:
            await message.answer("Оплата доступна только для заказов в работе/после предпросмотра.")
            return

        order.status = OrderStatus.PAID_ESCROW
        order.escrow_amount_rub = order.price_rub
        artist_tg = order.artist.tg_id

    await message.answer(
        (
            f"Escrow для заказа #{order_id} отмечен как оплаченный.\n"
            "Исполнитель может отправить финальный файл командой /send_art"
        )
    )
    await bot.send_message(
        artist_tg,
        f"Заказ #{order_id}: заказчик пополнил escrow на {order.price_rub} RUB.",
        protect_content=True,
    )


@router.message(Command("release"))
async def release_order(message: Message, bot: Bot) -> None:
    order_id = _extract_order_id(message)
    if order_id is None:
        await message.answer("Использование: /release <order_id>")
        return

    async with session_scope() as session:
        customer = await require_role(message, session, UserRole.CUSTOMER)
        if customer is None:
            return

        order = await get_order_by_id(session, order_id)
        if order is None:
            await message.answer("Заказ не найден.")
            return

        if order.customer_id != customer.id:
            await message.answer("Это не ваш заказ.")
            return

        if order.status not in {OrderStatus.FINAL_REVIEW, OrderStatus.PAID_ESCROW, OrderStatus.PREVIEW_SENT}:
            await message.answer("Релиз доступен после отправки финала/оплаты.")
            return

        premium = is_premium_active(order.artist.premium_until)
        commission = calculate_commission(order.price_rub, premium, order.commission_pct)
        payout = payout_amount(order.price_rub, commission)
        order.status = OrderStatus.COMPLETED
        artist_tg = order.artist.tg_id

    await message.answer(
        (
            f"Заказ #{order_id} завершен.\n"
            f"Комиссия платформы: {commission} RUB\n"
            f"К выплате исполнителю: {payout} RUB"
        )
    )
    await bot.send_message(
        artist_tg,
        (
            f"Заказ #{order_id} успешно завершен заказчиком.\n"
            f"К выплате (mock): {payout} RUB, комиссия: {commission} RUB"
        ),
        protect_content=True,
    )


@router.message(Command("dispute"))
async def dispute_order(message: Message, bot: Bot, settings: Settings) -> None:
    order_id = _extract_order_id(message)
    if order_id is None:
        await message.answer("Использование: /dispute <order_id>")
        return

    if message.from_user is None:
        return

    async with session_scope() as session:
        user = await require_registered_user(message, session)
        if user is None:
            return

        order = await get_order_by_id(session, order_id)
        if order is None:
            await message.answer("Заказ не найден.")
            return

        allowed = user.id in {order.customer_id, order.artist_id} or user.tg_id in settings.admin_ids
        if not allowed:
            await message.answer("Вы не участник этого заказа.")
            return

        order.status = OrderStatus.DISPUTED
        customer_tg = order.customer.tg_id
        artist_tg = order.artist.tg_id

    await message.answer(
        f"Спор по заказу #{order_id} открыт. Администратор рассмотрит его в течение 7 дней."
    )

    if message.from_user.id != customer_tg:
        await bot.send_message(customer_tg, f"По заказу #{order_id} открыт спор.", protect_content=True)
    if message.from_user.id != artist_tg:
        await bot.send_message(artist_tg, f"По заказу #{order_id} открыт спор.", protect_content=True)

    for admin_id in settings.admin_ids:
        if admin_id == message.from_user.id:
            continue
        await bot.send_message(
            admin_id,
            (
                f"[ADMIN] Новый спор\n"
                f"Заказ #{order_id}\n"
                f"Заказчик: {customer_tg}\n"
                f"Исполнитель: {artist_tg}"
            ),
        )


@router.message(Command("force_close"))
async def force_close_order(message: Message, bot: Bot) -> None:
    order_id = _extract_order_id(message)
    if order_id is None:
        await message.answer("Использование: /force_close <order_id>")
        return

    if message.from_user is None:
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
            await message.answer("Заказ уже закрыт.")
            return

        order.status = OrderStatus.CANCELLED
        customer_tg = order.customer.tg_id
        artist_tg = order.artist.tg_id

    await message.answer(f"Заказ #{order_id} закрыт принудительно.")
    if message.from_user.id != customer_tg:
        await bot.send_message(customer_tg, f"Заказ #{order_id} закрыт принудительно второй стороной.")
    if message.from_user.id != artist_tg:
        await bot.send_message(artist_tg, f"Заказ #{order_id} закрыт принудительно второй стороной.")


@router.callback_query(F.data.startswith("pay:"))
async def pay_callback(callback: CallbackQuery, bot: Bot) -> None:
    if callback.message is None:
        return
    await callback.answer("Используйте команду /pay <id>")


@router.callback_query(F.data.startswith("release:"))
async def release_callback(callback: CallbackQuery, bot: Bot) -> None:
    if callback.message is None:
        return
    await callback.answer("Используйте команду /release <id>")


@router.callback_query(F.data.startswith("dispute:"))
async def dispute_callback(callback: CallbackQuery, bot: Bot) -> None:
    if callback.message is None:
        return
    await callback.answer("Используйте команду /dispute <id>")
