from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
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
    wallet_connected: bool = True,
    language: str = DEFAULT_LANGUAGE,
) -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()

    if role == UserRole.CUSTOMER:
        if wallet_connected:
            kb.row(KeyboardButton(text=tr("btn_create_order", language)))
        if has_orders and wallet_connected:
            kb.row(KeyboardButton(text=tr("btn_my_orders", language)))
        kb.row(
            KeyboardButton(text=tr("btn_search", language)),
            KeyboardButton(text=tr("btn_report", language)),
        )
    elif role == UserRole.ARTIST:
        row: list[KeyboardButton] = []
        if can_send_art and wallet_connected:
            row.append(KeyboardButton(text=tr("btn_send_art", language)))
        if has_orders and wallet_connected:
            row.append(KeyboardButton(text=tr("btn_my_orders", language)))
        if row:
            kb.row(*row)
        kb.row(
            KeyboardButton(text=tr("btn_profile", language)),
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


def username_contact_menu(language: str = DEFAULT_LANGUAGE, username: str | None = None) -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    if username:
        kb.row(KeyboardButton(text=f"@{username}"))
    else:
        kb.row(KeyboardButton(text=tr("btn_share_username", language)))
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


def rules_article_keyboard(url: str, language: str = DEFAULT_LANGUAGE) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=tr("btn_rules_open_article", language), url=url)],
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


def dispute_confirm_keyboard(order_id: int, language: str = DEFAULT_LANGUAGE) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=tr("btn_yes", language),
                    callback_data=f"dispute_confirm:{order_id}:yes",
                ),
                InlineKeyboardButton(
                    text=tr("btn_no", language),
                    callback_data=f"dispute_confirm:{order_id}:no",
                ),
            ]
        ]
    )


def relay_open_inline_keyboard(order_id: int, language: str = DEFAULT_LANGUAGE) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=tr("btn_relay_open_now", language),
                    callback_data=f"relay_open:{order_id}",
                )
            ]
        ]
    )


def delete_paid_confirm_keyboard(order_id: int, language: str = DEFAULT_LANGUAGE) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=tr("btn_yes", language),
                    callback_data=f"delete_order_confirm:{order_id}:yes",
                ),
                InlineKeyboardButton(
                    text=tr("btn_no", language),
                    callback_data=f"delete_order_confirm:{order_id}:no",
                ),
            ]
        ]
    )


def search_type_keyboard(language: str = DEFAULT_LANGUAGE) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=tr("btn_search_by_username", language),
                    callback_data="search_type:username",
                )
            ],
            [
                InlineKeyboardButton(
                    text=tr("btn_search_random", language),
                    callback_data="search_type:random",
                )
            ],
        ]
    )


def open_profile_webapp_button(
    tg_id: int,
    miniapp_url: str,
    language: str = DEFAULT_LANGUAGE,
) -> InlineKeyboardButton | None:
    """Inline button that opens the profile mini app for `tg_id`.

    Returns None if no https mini app URL is configured — Telegram rejects
    non-https `web_app` buttons, so callers should just omit the row.
    """
    if not miniapp_url or not miniapp_url.startswith("https://"):
        return None
    return InlineKeyboardButton(
        text=tr("btn_open_profile", language),
        web_app=WebAppInfo(url=f"{miniapp_url}?profile_id={tg_id}"),
    )


def with_extra_row(
    markup: InlineKeyboardMarkup | None,
    button: InlineKeyboardButton | None,
) -> InlineKeyboardMarkup | None:
    """Append `button` as its own row to an existing (possibly None) markup."""
    if button is None:
        return markup
    rows = list(markup.inline_keyboard) if markup else []
    rows.append([button])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def artist_confirmation_keyboard(
    tg_id: int | None = None,
    miniapp_url: str = "",
    language: str = DEFAULT_LANGUAGE,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text=tr("btn_take_artist", language),
                callback_data="artist_confirm:take",
            ),
            InlineKeyboardButton(
                text=tr("btn_skip_artist", language),
                callback_data="artist_confirm:skip",
            ),
        ]
    ]
    if tg_id is not None:
        button = open_profile_webapp_button(tg_id, miniapp_url, language)
        if button:
            rows.append([button])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def profile_visibility_keyboard(language: str = DEFAULT_LANGUAGE) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=tr("btn_show_profile", language),
                    callback_data="profile_visibility:show",
                )
            ],
            [
                InlineKeyboardButton(
                    text=tr("btn_hide_profile", language),
                    callback_data="profile_visibility:hide",
                )
            ],
        ]
    )
