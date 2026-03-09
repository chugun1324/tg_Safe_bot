from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from artsecure_bot.models import UserRole


def role_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Заказчик", callback_data="reg_role:customer")
    kb.button(text="Исполнитель", callback_data="reg_role:artist")
    kb.adjust(2)
    return kb.as_markup()


def main_menu(role: UserRole) -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()

    if role == UserRole.CUSTOMER:
        kb.row(KeyboardButton(text="/create"), KeyboardButton(text="/my_orders"))
        kb.row(KeyboardButton(text="/search"), KeyboardButton(text="/report"))
    elif role == UserRole.ARTIST:
        kb.row(KeyboardButton(text="/send_art"), KeyboardButton(text="/my_orders"))
        kb.row(KeyboardButton(text="/search"), KeyboardButton(text="/report"))
    else:
        kb.row(KeyboardButton(text="/admin_stats"), KeyboardButton(text="/resolve"))

    kb.row(KeyboardButton(text="/rules"), KeyboardButton(text="/help"))
    return kb.as_markup(resize_keyboard=True)


def order_decision_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Принять", callback_data=f"order_decision:{order_id}:accept"
                ),
                InlineKeyboardButton(
                    text="Отклонить", callback_data=f"order_decision:{order_id}:reject"
                ),
            ]
        ]
    )


def art_kind_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Предпросмотр", callback_data="art_kind:preview")],
            [InlineKeyboardButton(text="Финал", callback_data="art_kind:final")],
        ]
    )


def order_actions_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Оплачено (escrow)", callback_data=f"pay:{order_id}")],
            [InlineKeyboardButton(text="Релиз исполнителю", callback_data=f"release:{order_id}")],
            [InlineKeyboardButton(text="Открыть спор", callback_data=f"dispute:{order_id}")],
        ]
    )
