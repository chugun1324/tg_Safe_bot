from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from artsecure_bot.i18n import DEFAULT_LANGUAGE, tr
from artsecure_bot.models import OrderStatus, UserRole


def role_keyboard(language: str = DEFAULT_LANGUAGE) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=tr("role_customer", language), callback_data="reg_role:customer")
    kb.button(text=tr("role_artist", language), callback_data="reg_role:artist")
    kb.adjust(2)
    return kb.as_markup()


def main_menu(
    role: UserRole,
    has_orders: bool = False,
    can_send_art: bool = False,
    language: str = DEFAULT_LANGUAGE,
) -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()

    if role == UserRole.CUSTOMER:
        kb.row(KeyboardButton(text=tr("btn_create_order", language)))
        if has_orders:
            kb.row(KeyboardButton(text=tr("btn_my_orders", language)))
        kb.row(
            KeyboardButton(text=tr("btn_search", language)),
            KeyboardButton(text=tr("btn_report", language)),
        )
    elif role == UserRole.ARTIST:
        row: list[KeyboardButton] = []
        if can_send_art:
            row.append(KeyboardButton(text=tr("btn_send_art", language)))
        if has_orders:
            row.append(KeyboardButton(text=tr("btn_my_orders", language)))
        if row:
            kb.row(*row)
        kb.row(
            KeyboardButton(text=tr("btn_search", language)),
            KeyboardButton(text=tr("btn_report", language)),
        )
    else:
        kb.row(KeyboardButton(text=tr("btn_admin_stats", language)))

    kb.row(KeyboardButton(text=tr("btn_rules", language)), KeyboardButton(text=tr("btn_help", language)))
    kb.row(
        KeyboardButton(text=tr("btn_wallet", language)),
        KeyboardButton(text=tr("btn_language", language)),
    )
    kb.row(KeyboardButton(text=tr("btn_exit", language)))
    return kb.as_markup(resize_keyboard=True)


def flow_menu(language: str = DEFAULT_LANGUAGE) -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.row(KeyboardButton(text=tr("btn_cancel", language)))
    kb.row(KeyboardButton(text=tr("btn_rules", language)), KeyboardButton(text=tr("btn_help", language)))
    kb.row(KeyboardButton(text=tr("btn_language", language)))
    kb.row(KeyboardButton(text=tr("btn_exit", language)))
    return kb.as_markup(resize_keyboard=True)


def relay_menu(
    language: str = DEFAULT_LANGUAGE,
    can_send_art: bool = False,
    can_mark_done: bool = False,
) -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.row(KeyboardButton(text=tr("btn_leave_relay", language)))
    row: list[KeyboardButton] = []
    if can_send_art:
        row.append(KeyboardButton(text=tr("btn_send_art", language)))
    if can_mark_done:
        row.append(KeyboardButton(text=tr("btn_mark_done", language)))
    if row:
        kb.row(*row)
    kb.row(KeyboardButton(text=tr("btn_rules", language)), KeyboardButton(text=tr("btn_help", language)))
    kb.row(KeyboardButton(text=tr("btn_language", language)))
    kb.row(KeyboardButton(text=tr("btn_exit", language)))
    return kb.as_markup(resize_keyboard=True)


def order_decision_keyboard(order_id: int, language: str = DEFAULT_LANGUAGE) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=tr("order_decision_accept", language),
                    callback_data=f"order_decision:{order_id}:accept",
                ),
                InlineKeyboardButton(
                    text=tr("order_decision_reject", language),
                    callback_data=f"order_decision:{order_id}:reject",
                ),
            ]
        ]
    )


def art_kind_keyboard(language: str = DEFAULT_LANGUAGE) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=tr("art_kind_direct", language), callback_data="art_kind:direct")],
        ]
    )


def order_actions_keyboard(
    order_id: int,
    status: OrderStatus,
    role: UserRole,
    language: str = DEFAULT_LANGUAGE,
) -> InlineKeyboardMarkup | None:
    rows: list[list[InlineKeyboardButton]] = []
    is_active = status not in {OrderStatus.CANCELLED, OrderStatus.COMPLETED}
    relay_allowed = status in {
        OrderStatus.IN_PROGRESS,
        OrderStatus.PREVIEW_SENT,
        OrderStatus.PAID_ESCROW,
        OrderStatus.PENDING_REVIEW,
        OrderStatus.FINAL_REVIEW,
        OrderStatus.DISPUTED,
    }

    if relay_allowed:
        rows.append(
            [
                InlineKeyboardButton(
                    text=tr("order_action_relay", language),
                    callback_data=f"relay_open:{order_id}",
                )
            ]
        )

    if role == UserRole.CUSTOMER:
        if status in {OrderStatus.IN_PROGRESS, OrderStatus.PREVIEW_SENT}:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=tr("order_action_paid", language),
                        callback_data=f"pay:{order_id}",
                    )
                ]
            )
        if status in {OrderStatus.PAID_ESCROW, OrderStatus.FINAL_REVIEW}:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=tr("order_action_release", language),
                        callback_data=f"release:{order_id}",
                    )
                ]
            )
        if is_active:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=tr("order_action_dispute", language),
                        callback_data=f"dispute:{order_id}",
                    )
                ]
            )
        rows.append(
            [
                InlineKeyboardButton(
                    text=tr("order_action_delete", language),
                    callback_data=f"delete_order:{order_id}",
                )
            ]
        )
    elif role == UserRole.ARTIST and is_active:
        rows.append(
            [
                InlineKeyboardButton(
                    text=tr("order_action_dispute", language),
                    callback_data=f"dispute:{order_id}",
                )
            ]
        )

    if not rows:
        return None
    return InlineKeyboardMarkup(inline_keyboard=rows)


def language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=tr("lang_ru", "ru"), callback_data="set_lang:ru")],
            [InlineKeyboardButton(text=tr("lang_en", "en"), callback_data="set_lang:en")],
        ]
    )


def order_currency_keyboard(language: str = DEFAULT_LANGUAGE) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=tr("currency_rub", language), callback_data="order_currency:RUB")],
            [InlineKeyboardButton(text=tr("currency_usd", language), callback_data="order_currency:USD")],
            [InlineKeyboardButton(text=tr("currency_usdt", language), callback_data="order_currency:USDT")],
        ]
    )


def dispute_reason_keyboard(order_id: int, language: str = DEFAULT_LANGUAGE) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=tr("dispute_reason_not_order", language),
                    callback_data=f"dispute_reason:not_order:{order_id}",
                ),
                InlineKeyboardButton(
                    text=tr("dispute_reason_other", language),
                    callback_data=f"dispute_reason:other:{order_id}",
                ),
            ]
        ]
    )
