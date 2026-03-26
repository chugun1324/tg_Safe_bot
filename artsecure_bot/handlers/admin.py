from __future__ import annotations

import html
import io
import os
import zipfile

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardRemove,
)

from artsecure_bot.config import Settings
from artsecure_bot.db import session_scope
from artsecure_bot.handlers.utils import build_main_menu_for_user
from artsecure_bot.i18n import tr, variants
from artsecure_bot.models import ArtAsset, Order, OrderStatus, Report, ReportStatus, User, UserRole
from artsecure_bot.services.chat_cleanup import clear_chat_keep_message
from artsecure_bot.services.order_logic import calculate_commission, is_premium_active
from artsecure_bot.services.repository import (
    add_to_blacklist,
    get_order_by_id,
    get_stats,
    get_user_by_id,
    get_user_by_tg_id,
    get_user_by_username,
    get_user_language,
    list_disputed_orders,
    list_reports,
    list_users,
)
from artsecure_bot.states import AdminState

router = Router()
PAGE_SIZE = 10
ADMIN_USERS_VIEW_LIMIT = 10


def _is_admin(message: Message, settings: Settings) -> bool:
    if message.from_user is None:
        return False
    return message.from_user.id in settings.admin_ids


def _is_admin_callback(callback: CallbackQuery, settings: Settings) -> bool:
    return callback.from_user is not None and callback.from_user.id in settings.admin_ids


def _admin_home_keyboard(language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=tr("admin_btn_disputes", language),
                    callback_data="admin:disputes:0",
                ),
                InlineKeyboardButton(
                    text=tr("admin_btn_reports", language),
                    callback_data="admin:reports:0",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=tr("admin_btn_blocks", language),
                    callback_data="admin:blocks:0",
                ),
                InlineKeyboardButton(
                    text=tr("admin_btn_users", language),
                    callback_data="admin:users:0",
                ),
            ],
            [InlineKeyboardButton(text=tr("admin_btn_exit_panel", language), callback_data="admin:exit")],
        ]
    )


def _single_back_keyboard(language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=tr("admin_btn_back", language),
                    callback_data="admin:home",
                )
            ]
        ]
    )


def _users_list_keyboard(users: list[User], offset: int, total: int, language: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for user in users:
        status_key = "admin_user_blocked" if user.is_banned else "admin_user_active"
        username_label = (
            f"@{user.username.lstrip('@')}" if user.username else tr("admin_user_no_username", language)
        )
        rows.append(
            [
                InlineKeyboardButton(
                    text=tr("admin_toggle_user", language, username=username_label, status=tr(status_key, language)),
                    callback_data=f"admin:toggle:{user.id}:{offset}",
                )
            ]
        )

    nav: list[InlineKeyboardButton] = []
    if offset > 0:
        nav.append(
            InlineKeyboardButton(
                text=tr("admin_btn_prev", language),
                callback_data=f"admin:blocks:{max(offset - PAGE_SIZE, 0)}",
            )
        )
    if offset + PAGE_SIZE < total:
        nav.append(
            InlineKeyboardButton(
                text=tr("admin_btn_next", language),
                callback_data=f"admin:blocks:{offset + PAGE_SIZE}",
            )
        )
    if nav:
        rows.append(nav)
    rows.append(
        [
            InlineKeyboardButton(
                text=tr("admin_btn_search", language),
                callback_data="admin:blocks_search",
            )
        ]
    )
    rows.append([InlineKeyboardButton(text=tr("admin_btn_back", language), callback_data="admin:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _users_db_keyboard(offset: int, total: int, language: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    nav: list[InlineKeyboardButton] = []
    if offset > 0:
        nav.append(
            InlineKeyboardButton(
                text=tr("admin_btn_prev", language),
                callback_data=f"admin:users:{max(offset - PAGE_SIZE, 0)}",
            )
        )
    if offset + PAGE_SIZE < total:
        nav.append(
            InlineKeyboardButton(
                text=tr("admin_btn_next", language),
                callback_data=f"admin:users:{offset + PAGE_SIZE}",
            )
        )
    if nav:
        rows.append(nav)
    rows.append(
        [
            InlineKeyboardButton(
                text=tr("admin_btn_search", language),
                callback_data="admin:users_search",
            )
        ]
    )
    rows.append([InlineKeyboardButton(text=tr("admin_btn_back", language), callback_data="admin:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _disputes_keyboard(orders: list[Order], offset: int, total: int, language: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for order in orders:
        rows.append(
            [
                InlineKeyboardButton(
                    text=tr("admin_dispute_row_button", language, order_id=order.id),
                    callback_data=f"admin:dispute:{order.id}",
                )
            ]
        )
    nav: list[InlineKeyboardButton] = []
    if offset > 0:
        nav.append(
            InlineKeyboardButton(
                text=tr("admin_btn_prev", language),
                callback_data=f"admin:disputes:{max(offset - PAGE_SIZE, 0)}",
            )
        )
    if offset + PAGE_SIZE < total:
        nav.append(
            InlineKeyboardButton(
                text=tr("admin_btn_next", language),
                callback_data=f"admin:disputes:{offset + PAGE_SIZE}",
            )
        )
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text=tr("admin_btn_back", language), callback_data="admin:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _report_keyboard(report_id: int, index: int, total: int, language: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    nav: list[InlineKeyboardButton] = []
    if index > 0:
        nav.append(
            InlineKeyboardButton(
                text=tr("admin_btn_prev", language),
                callback_data=f"admin:reports:{index - 1}",
            )
        )
    if index + 1 < total:
        nav.append(
            InlineKeyboardButton(
                text=tr("admin_btn_next", language),
                callback_data=f"admin:reports:{index + 1}",
            )
        )
    if nav:
        rows.append(nav)
    rows.append(
        [
            InlineKeyboardButton(
                text=tr("admin_btn_report_close", language),
                callback_data=f"admin:report_close:{report_id}:{index}",
            )
        ]
    )
    rows.append([InlineKeyboardButton(text=tr("admin_btn_back", language), callback_data="admin:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _dispute_details_keyboard(order_id: int, language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=tr("admin_btn_resolve_refund", language),
                    callback_data=f"admin:resolve:{order_id}:refund",
                ),
                InlineKeyboardButton(
                    text=tr("admin_btn_resolve_release", language),
                    callback_data=f"admin:resolve:{order_id}:release",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=tr("admin_btn_dispute_close", language),
                    callback_data=f"admin:dispute_close:{order_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=tr("admin_btn_back_disputes", language),
                    callback_data="admin:disputes:0",
                )
            ],
            [InlineKeyboardButton(text=tr("admin_btn_back", language), callback_data="admin:home")],
        ]
    )


def _parse_offset(data: str | None, section: str) -> int | None:
    if data is None:
        return None
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != "admin" or parts[1] != section or not parts[2].isdigit():
        return None
    return int(parts[2])


def _parse_dispute_id(data: str | None) -> int | None:
    if data is None:
        return None
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != "admin" or parts[1] != "dispute" or not parts[2].isdigit():
        return None
    return int(parts[2])


def _parse_toggle(data: str | None) -> tuple[int, int] | None:
    if data is None:
        return None
    parts = data.split(":")
    if (
        len(parts) != 4
        or parts[0] != "admin"
        or parts[1] != "toggle"
        or not parts[2].isdigit()
        or not parts[3].isdigit()
    ):
        return None
    return int(parts[2]), int(parts[3])


def _parse_resolve(data: str | None) -> tuple[int, str] | None:
    if data is None:
        return None
    parts = data.split(":")
    if len(parts) != 4 or parts[0] != "admin" or parts[1] != "resolve" or not parts[2].isdigit():
        return None
    if parts[3] not in {"refund", "release"}:
        return None
    return int(parts[2]), parts[3]


def _parse_dispute_close(data: str | None) -> int | None:
    if data is None:
        return None
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != "admin" or parts[1] != "dispute_close" or not parts[2].isdigit():
        return None
    return int(parts[2])


def _parse_report_close(data: str | None) -> tuple[int, int] | None:
    if data is None:
        return None
    parts = data.split(":")
    if (
        len(parts) != 4
        or parts[0] != "admin"
        or parts[1] != "report_close"
        or not parts[2].isdigit()
        or not parts[3].isdigit()
    ):
        return None
    return int(parts[2]), int(parts[3])


def _role_label(role: UserRole, language: str) -> str:
    if role == UserRole.CUSTOMER:
        return tr("role_customer", language)
    if role == UserRole.ARTIST:
        return tr("role_artist", language)
    return tr("role_admin", language)


def _user_mention(user: User | None, language: str) -> str:
    if user is None:
        return tr("unknown", language)
    if user.username:
        username = user.username.lstrip("@")
        return f'<a href="https://t.me/{username}">@{username}</a>'
    return f'<a href="tg://user?id={user.tg_id}">{tr("admin_user_open_profile", language)}</a>'


def _normalize_admin_user_query(raw: str) -> tuple[str, str] | None:
    value = raw.strip()
    if not value:
        return None
    if value.startswith("@"):
        username = value.lstrip("@").strip()
        if not username:
            return None
        return "username", username
    if value.isdigit():
        return "tg_id", value
    return None


async def _build_artist_assets_zip(bot: Bot, order: Order) -> tuple[bytes | None, int]:
    artist_assets: list[ArtAsset] = [asset for asset in order.assets if asset.sender_id == order.artist_id]
    if not artist_assets:
        return None, 0

    output = io.BytesIO()
    added_count = 0
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as zipf:
        for asset in artist_assets:
            file_id = asset.original_file_id or asset.watermarked_file_id
            if not file_id:
                continue
            try:
                file = await bot.get_file(file_id)
                destination = io.BytesIO()
                await bot.download_file(file.file_path, destination=destination)
            except Exception:
                if asset.original_file_id and asset.watermarked_file_id and file_id == asset.original_file_id:
                    try:
                        file = await bot.get_file(asset.watermarked_file_id)
                        destination = io.BytesIO()
                        await bot.download_file(file.file_path, destination=destination)
                    except Exception:
                        continue
                else:
                    continue
            ext = os.path.splitext(file.file_path or "")[1] or ".bin"
            zip_name = f"order_{order.id}_asset_{asset.id}{ext}"
            zipf.writestr(zip_name, destination.getvalue())
            added_count += 1

    if added_count == 0:
        return None, 0
    return output.getvalue(), added_count


def _format_reports_page(
    report: Report,
    reporter: User | None,
    target: User | None,
    index: int,
    total: int,
    language: str,
) -> str:
    created = report.created_at.strftime("%Y-%m-%d %H:%M:%S")
    order_id = report.order_id if report.order_id is not None else "-"
    return tr(
        "admin_reports_card",
        language,
        index=index + 1,
        total=total,
        report_id=report.id,
        created_at=created,
        order_id=order_id,
        reporter_ref=_user_mention(reporter, language),
        target_ref=_user_mention(target, language),
        status=html.escape(report.status.value),
        reason=html.escape(report.reason),
    )


def _format_users_page(users: list[User], total: int, offset: int, language: str) -> str:
    header = tr("admin_users_header", language, start=offset + 1, end=offset + len(users), total=total)
    lines: list[str] = [header]
    for user in users:
        lines.append(
            tr(
                "admin_users_row",
                language,
                user_id=user.id,
                user_ref=_user_mention(user, language),
                role=_role_label(user.role, language),
                status=tr("admin_user_blocked", language) if user.is_banned else tr("admin_user_active", language),
            )
        )
    return "\n".join(lines)


def _format_found_user_card(user: User, language: str) -> str:
    return tr(
        "admin_user_found_card",
        language,
        user_id=user.id,
        user_ref=_user_mention(user, language),
        role=_role_label(user.role, language),
        status=tr("admin_user_blocked", language) if user.is_banned else tr("admin_user_active", language),
    )


def _found_user_keyboard(user: User, for_blocks: bool, language: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if for_blocks:
        rows.append(
            [
                InlineKeyboardButton(
                    text=tr("admin_btn_toggle_found_user", language),
                    callback_data=f"admin:toggle:{user.id}:0",
                )
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(
                    text=tr("admin_btn_back_blocks", language),
                    callback_data="admin:blocks:0",
                )
            ]
        )
    else:
        rows.append(
            [
                InlineKeyboardButton(
                    text=tr("admin_btn_back_users", language),
                    callback_data="admin:users:0",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text=tr("admin_btn_back", language), callback_data="admin:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _search_input_keyboard(section: str, language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=tr("admin_btn_back_section", language), callback_data=f"admin:{section}:0")],
            [InlineKeyboardButton(text=tr("admin_btn_back", language), callback_data="admin:home")],
        ]
    )


@router.message(Command("admin"))
async def admin_panel(message: Message, state: FSMContext, settings: Settings) -> None:
    if message.from_user is None or message.from_user.id not in settings.admin_ids:
        return
    await state.clear()
    async with session_scope() as session:
        lang = await get_user_language(session, message.from_user.id)
    await message.answer(tr("admin_panel_entering", lang), reply_markup=ReplyKeyboardRemove())
    panel_message = await message.answer(
        tr("admin_panel_welcome", lang),
        reply_markup=_admin_home_keyboard(lang),
    )
    await clear_chat_keep_message(message.bot, message.chat.id, panel_message.message_id)


@router.callback_query(F.data == "admin:home")
async def admin_home(callback: CallbackQuery, state: FSMContext, settings: Settings) -> None:
    if callback.message is None or not _is_admin_callback(callback, settings):
        await callback.answer()
        return
    await state.clear()
    async with session_scope() as session:
        lang = await get_user_language(session, callback.from_user.id)
    await callback.message.edit_text(tr("admin_panel_welcome", lang), reply_markup=_admin_home_keyboard(lang))
    await callback.answer()


@router.callback_query(F.data == "admin:exit")
async def admin_exit(callback: CallbackQuery, state: FSMContext, settings: Settings) -> None:
    if callback.message is None or callback.from_user is None or not _is_admin_callback(callback, settings):
        await callback.answer()
        return
    await state.clear()
    async with session_scope() as session:
        lang = await get_user_language(session, callback.from_user.id)
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if user is not None:
            menu = await build_main_menu_for_user(session, user)
        else:
            menu = ReplyKeyboardRemove()

    await callback.message.edit_text(tr("admin_panel_closed", lang))
    await callback.message.answer(tr("admin_panel_back_to_user", lang), reply_markup=menu)
    await callback.answer()


@router.callback_query(F.data.startswith("admin:disputes:"))
async def admin_disputes(callback: CallbackQuery, state: FSMContext, settings: Settings) -> None:
    if callback.message is None or not _is_admin_callback(callback, settings):
        await callback.answer()
        return
    await state.clear()
    offset = _parse_offset(callback.data, "disputes")
    if offset is None:
        await callback.answer()
        return
    async with session_scope() as session:
        lang = await get_user_language(session, callback.from_user.id)
        disputed = await list_disputed_orders(session, limit=100)
    if not disputed:
        await callback.message.edit_text(
            tr("admin_disputes_empty", lang),
            reply_markup=_single_back_keyboard(lang),
        )
        await callback.answer()
        return

    normalized_offset = max(0, min(offset, max(0, len(disputed) - 1)))
    page_orders = disputed[normalized_offset : normalized_offset + PAGE_SIZE]
    lines = [tr("admin_disputes_title", lang, count=len(disputed))]
    for order in page_orders:
        lines.append(
            tr(
                "admin_disputes_row",
                lang,
                order_id=order.id,
                customer_ref=_user_mention(order.customer, lang),
                artist_ref=_user_mention(order.artist, lang),
                price=order.price_rub,
            )
        )
    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=_disputes_keyboard(page_orders, normalized_offset, len(disputed), lang),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:dispute:"))
async def admin_dispute_open(callback: CallbackQuery, bot: Bot, settings: Settings) -> None:
    if callback.message is None or not _is_admin_callback(callback, settings):
        await callback.answer()
        return
    order_id = _parse_dispute_id(callback.data)
    if order_id is None:
        await callback.answer()
        return

    archive_bytes: bytes | None = None
    added_files = 0
    async with session_scope() as session:
        lang = await get_user_language(session, callback.from_user.id)
        order = await get_order_by_id(session, order_id)
        if order is None:
            await callback.answer(tr("order_not_found", lang), show_alert=True)
            return
        archive_bytes, added_files = await _build_artist_assets_zip(bot, order)
        text = tr(
            "admin_dispute_card",
            lang,
            order_id=order.id,
            status=html.escape(order.status.value),
            customer_ref=_user_mention(order.customer, lang),
            artist_ref=_user_mention(order.artist, lang),
            title=html.escape(order.title),
            price=order.price_rub,
            assets=added_files,
        )

    await callback.message.edit_text(text, reply_markup=_dispute_details_keyboard(order_id, lang))
    if archive_bytes is not None:
        await bot.send_document(
            callback.from_user.id,
            BufferedInputFile(archive_bytes, filename=f"order_{order_id}_artist_media.zip"),
            caption=tr("admin_dispute_zip_caption", lang, order_id=order_id, files=added_files),
            protect_content=True,
        )
    else:
        await bot.send_message(callback.from_user.id, tr("admin_dispute_zip_empty", lang, order_id=order_id))
    await callback.answer()


@router.callback_query(F.data.startswith("admin:dispute_close:"))
async def admin_dispute_close(callback: CallbackQuery, bot: Bot, settings: Settings) -> None:
    if callback.message is None or callback.from_user is None or not _is_admin_callback(callback, settings):
        await callback.answer()
        return
    order_id = _parse_dispute_close(callback.data)
    if order_id is None:
        await callback.answer()
        return

    async with session_scope() as session:
        lang = await get_user_language(session, callback.from_user.id)
        order = await get_order_by_id(session, order_id)
        if order is None:
            await callback.answer(tr("order_not_found", lang), show_alert=True)
            return
        if order.status != OrderStatus.DISPUTED:
            await callback.answer(tr("admin_dispute_not_open", lang), show_alert=True)
            return
        restore_status = order.status_before_dispute or OrderStatus.IN_PROGRESS
        order.status = restore_status
        order.status_before_dispute = None
        customer_tg = order.customer.tg_id
        artist_tg = order.artist.tg_id
        customer_lang = await get_user_language(session, customer_tg)
        artist_lang = await get_user_language(session, artist_tg)

    await callback.answer(tr("admin_dispute_closed", lang), show_alert=True)
    await callback.message.edit_text(
        tr("admin_dispute_closed_text", lang, order_id=order_id),
        reply_markup=_single_back_keyboard(lang),
    )
    await bot.send_message(
        customer_tg,
        tr("admin_dispute_closed_notify", customer_lang, order_id=order_id),
        protect_content=True,
    )
    await bot.send_message(
        artist_tg,
        tr("admin_dispute_closed_notify", artist_lang, order_id=order_id),
        protect_content=True,
    )


@router.callback_query(F.data.startswith("admin:resolve:"))
async def admin_resolve_callback(callback: CallbackQuery, bot: Bot, settings: Settings) -> None:
    if callback.from_user is None or callback.message is None or not _is_admin_callback(callback, settings):
        await callback.answer()
        return
    parsed = _parse_resolve(callback.data)
    if parsed is None:
        await callback.answer()
        return
    order_id, decision = parsed

    async with session_scope() as session:
        lang = await get_user_language(session, callback.from_user.id)
        order = await get_order_by_id(session, order_id)
        if order is None:
            await callback.answer(tr("order_not_found", lang), show_alert=True)
            return

        customer_tg = order.customer.tg_id
        artist_tg = order.artist.tg_id
        customer_lang = await get_user_language(session, customer_tg)
        artist_lang = await get_user_language(session, artist_tg)

        if decision == "refund":
            order.status = OrderStatus.CANCELLED
            order.status_before_dispute = None
            customer_msg = tr("admin_refund_customer", customer_lang, order_id=order_id)
            artist_msg = tr("admin_refund_artist", artist_lang, order_id=order_id)
        else:
            order.status = OrderStatus.COMPLETED
            order.status_before_dispute = None
            commission = calculate_commission(
                order.price_rub,
                is_premium_active(order.artist.premium_until),
                order.commission_pct,
            )
            payout = max(order.price_rub - commission, 0)
            customer_msg = tr("admin_release_customer", customer_lang, order_id=order_id, payout=payout)
            artist_msg = tr("admin_release_artist", artist_lang, order_id=order_id, payout=payout)

    await callback.answer()
    await callback.message.answer(tr("admin_resolve_done", lang, order_id=order_id, decision=decision))
    await bot.send_message(customer_tg, customer_msg, protect_content=True)
    await bot.send_message(artist_tg, artist_msg, protect_content=True)
    await callback.message.edit_reply_markup(reply_markup=_single_back_keyboard(lang))


@router.callback_query(F.data.startswith("admin:reports:"))
async def admin_reports(callback: CallbackQuery, state: FSMContext, settings: Settings) -> None:
    if callback.message is None or not _is_admin_callback(callback, settings):
        await callback.answer()
        return
    await state.clear()
    index = _parse_offset(callback.data, "reports")
    if index is None:
        await callback.answer()
        return

    async with session_scope() as session:
        lang = await get_user_language(session, callback.from_user.id)
        reports = [item for item in await list_reports(session, limit=300) if item.status == ReportStatus.OPEN]
        if not reports:
            await callback.message.edit_text(
                tr("admin_reports_empty", lang),
                reply_markup=_single_back_keyboard(lang),
            )
            await callback.answer()
            return

        current = max(0, min(index, len(reports) - 1))
        report = reports[current]
        reporter = await get_user_by_id(session, report.reporter_id)
        target = await get_user_by_id(session, report.target_user_id)
        text = _format_reports_page(report, reporter, target, current, len(reports), lang)

    await callback.message.edit_text(text, reply_markup=_report_keyboard(report.id, current, len(reports), lang))
    await callback.answer()


@router.callback_query(F.data.startswith("admin:report_close:"))
async def admin_report_close(callback: CallbackQuery, settings: Settings) -> None:
    if callback.message is None or callback.from_user is None or not _is_admin_callback(callback, settings):
        await callback.answer()
        return
    parsed = _parse_report_close(callback.data)
    if parsed is None:
        await callback.answer()
        return
    report_id, fallback_index = parsed

    async with session_scope() as session:
        lang = await get_user_language(session, callback.from_user.id)
        reports = await list_reports(session, limit=300)
        report = next((item for item in reports if item.id == report_id), None)
        if report is None:
            await callback.answer(tr("admin_report_not_found", lang), show_alert=True)
            return
        report.status = ReportStatus.RESOLVED

    await callback.answer(tr("admin_report_closed", lang), show_alert=True)

    async with session_scope() as session:
        lang = await get_user_language(session, callback.from_user.id)
        reports = [item for item in await list_reports(session, limit=300) if item.status == ReportStatus.OPEN]
        if not reports:
            await callback.message.edit_text(
                tr("admin_reports_empty", lang),
                reply_markup=_single_back_keyboard(lang),
            )
            return
        current = max(0, min(fallback_index, len(reports) - 1))
        current_report = reports[current]
        reporter = await get_user_by_id(session, current_report.reporter_id)
        target = await get_user_by_id(session, current_report.target_user_id)
        text = _format_reports_page(current_report, reporter, target, current, len(reports), lang)
        markup = _report_keyboard(current_report.id, current, len(reports), lang)
    await callback.message.edit_text(text, reply_markup=markup)


@router.callback_query(F.data.startswith("admin:blocks:"))
async def admin_blocks(callback: CallbackQuery, state: FSMContext, settings: Settings) -> None:
    if callback.message is None or not _is_admin_callback(callback, settings):
        await callback.answer()
        return
    await state.clear()
    offset = _parse_offset(callback.data, "blocks")
    if offset is None:
        await callback.answer()
        return

    async with session_scope() as session:
        lang = await get_user_language(session, callback.from_user.id)
        users = await list_users(session, limit=ADMIN_USERS_VIEW_LIMIT)
        if not users:
            await callback.message.edit_text(
                tr("admin_users_empty", lang),
                reply_markup=_single_back_keyboard(lang),
            )
            await callback.answer()
            return
        normalized_offset = max(0, min(offset, max(0, len(users) - 1)))
        page_users = users[normalized_offset : normalized_offset + PAGE_SIZE]
        text = _format_users_page(page_users, len(users), normalized_offset, lang)
        keyboard = _users_list_keyboard(page_users, normalized_offset, len(users), lang)

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("admin:toggle:"))
async def admin_toggle_user(callback: CallbackQuery, settings: Settings) -> None:
    if callback.message is None or callback.from_user is None or not _is_admin_callback(callback, settings):
        await callback.answer()
        return
    parsed = _parse_toggle(callback.data)
    if parsed is None:
        await callback.answer()
        return
    user_id, offset = parsed

    async with session_scope() as session:
        lang = await get_user_language(session, callback.from_user.id)
        user = await get_user_by_id(session, user_id)
        if user is None:
            await callback.answer(tr("user_not_found", lang), show_alert=True)
            return
        user.is_banned = not user.is_banned
        if user.is_banned:
            await add_to_blacklist(
                session=session,
                user_id=user.id,
                reason=tr("admin_block_reason", lang),
                created_by_tg_id=callback.from_user.id,
            )
        toggle_text = tr(
            "admin_toggle_done",
            lang,
            username=f"@{user.username.lstrip('@')}" if user.username else tr("admin_user_no_username", lang),
            status=tr("admin_user_blocked", lang) if user.is_banned else tr("admin_user_active", lang),
        )
    await callback.answer(toggle_text, show_alert=True)

    async with session_scope() as session:
        lang = await get_user_language(session, callback.from_user.id)
        users = await list_users(session, limit=ADMIN_USERS_VIEW_LIMIT)
        if not users:
            await callback.message.edit_text(
                tr("admin_users_empty", lang),
                reply_markup=_single_back_keyboard(lang),
            )
            return
        normalized_offset = max(0, min(offset, max(0, len(users) - 1)))
        page_users = users[normalized_offset : normalized_offset + PAGE_SIZE]
        text = _format_users_page(page_users, len(users), normalized_offset, lang)
        keyboard = _users_list_keyboard(page_users, normalized_offset, len(users), lang)
    await callback.message.edit_text(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("admin:users:"))
async def admin_users_db(callback: CallbackQuery, state: FSMContext, settings: Settings) -> None:
    if callback.message is None or not _is_admin_callback(callback, settings):
        await callback.answer()
        return
    await state.clear()
    offset = _parse_offset(callback.data, "users")
    if offset is None:
        await callback.answer()
        return

    async with session_scope() as session:
        lang = await get_user_language(session, callback.from_user.id)
        users = await list_users(session, limit=ADMIN_USERS_VIEW_LIMIT)
        if not users:
            await callback.message.edit_text(
                tr("admin_users_empty", lang),
                reply_markup=_single_back_keyboard(lang),
            )
            await callback.answer()
            return

        normalized_offset = max(0, min(offset, max(0, len(users) - 1)))
        page_users = users[normalized_offset : normalized_offset + PAGE_SIZE]
        text = _format_users_page(page_users, len(users), normalized_offset, lang)
        keyboard = _users_db_keyboard(normalized_offset, len(users), lang)

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "admin:blocks_search")
async def admin_blocks_search_start(callback: CallbackQuery, state: FSMContext, settings: Settings) -> None:
    if callback.message is None or not _is_admin_callback(callback, settings):
        await callback.answer()
        return
    async with session_scope() as session:
        lang = await get_user_language(session, callback.from_user.id)
    await state.set_state(AdminState.waiting_blocks_query)
    await callback.message.edit_text(
        tr("admin_search_prompt", lang),
        reply_markup=_search_input_keyboard("blocks", lang),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:users_search")
async def admin_users_search_start(callback: CallbackQuery, state: FSMContext, settings: Settings) -> None:
    if callback.message is None or not _is_admin_callback(callback, settings):
        await callback.answer()
        return
    async with session_scope() as session:
        lang = await get_user_language(session, callback.from_user.id)
    await state.set_state(AdminState.waiting_users_query)
    await callback.message.edit_text(
        tr("admin_search_prompt", lang),
        reply_markup=_search_input_keyboard("users", lang),
    )
    await callback.answer()


@router.message(AdminState.waiting_blocks_query)
async def admin_blocks_search_input(message: Message, state: FSMContext, settings: Settings) -> None:
    if message.from_user is None or message.from_user.id not in settings.admin_ids:
        return
    if (message.text or "").startswith("/"):
        return
    async with session_scope() as session:
        lang = await get_user_language(session, message.from_user.id)
        parsed = _normalize_admin_user_query(message.text or "")
        if parsed is None:
            await message.answer(tr("admin_search_invalid", lang))
            return
        mode, value = parsed
        if mode == "tg_id":
            user = await get_user_by_tg_id(session, int(value))
        else:
            user = await get_user_by_username(session, value)
        if user is None:
            await message.answer(tr("admin_user_not_found_search", lang))
            return
        text = _format_found_user_card(user, lang)
        keyboard = _found_user_keyboard(user, for_blocks=True, language=lang)
    await state.clear()
    await message.answer(text, reply_markup=keyboard)


@router.message(AdminState.waiting_users_query)
async def admin_users_search_input(message: Message, state: FSMContext, settings: Settings) -> None:
    if message.from_user is None or message.from_user.id not in settings.admin_ids:
        return
    if (message.text or "").startswith("/"):
        return
    async with session_scope() as session:
        lang = await get_user_language(session, message.from_user.id)
        parsed = _normalize_admin_user_query(message.text or "")
        if parsed is None:
            await message.answer(tr("admin_search_invalid", lang))
            return
        mode, value = parsed
        if mode == "tg_id":
            user = await get_user_by_tg_id(session, int(value))
        else:
            user = await get_user_by_username(session, value)
        if user is None:
            await message.answer(tr("admin_user_not_found_search", lang))
            return
        text = _format_found_user_card(user, lang)
        keyboard = _found_user_keyboard(user, for_blocks=False, language=lang)
    await state.clear()
    await message.answer(text, reply_markup=keyboard)


@router.message(Command("admin_stats"))
@router.message(F.text.in_(variants("btn_admin_stats")))
async def admin_stats(message: Message, settings: Settings) -> None:
    if message.from_user is None:
        return
    async with session_scope() as session:
        lang = await get_user_language(session, message.from_user.id)
        if not _is_admin(message, settings):
            await message.answer(tr("admin_only", lang))
            return
        stats = await get_stats(session)

    await message.answer(
        tr(
            "admin_stats",
            lang,
            total_orders=stats["total_orders"],
            completed_orders=stats["completed_orders"],
            disputed_orders=stats["disputed_orders"],
            gross_rub=stats["gross_rub"],
        )
    )


@router.message(Command("ban"))
async def admin_ban(message: Message, settings: Settings) -> None:
    if message.from_user is None:
        return
    async with session_scope() as session:
        lang = await get_user_language(session, message.from_user.id)
        if not _is_admin(message, settings):
            await message.answer(tr("admin_only", lang))
            return

        parts = (message.text or "").split(maxsplit=2)
        if len(parts) < 3 or not parts[1].isdigit():
            await message.answer(tr("usage_ban", lang))
            return

        tg_id = int(parts[1])
        reason = parts[2].strip()
        user = await get_user_by_tg_id(session, tg_id)
        if user is None:
            await message.answer(tr("user_not_found", lang))
            return

        user.is_banned = True
        await add_to_blacklist(
            session=session,
            user_id=user.id,
            reason=reason,
            created_by_tg_id=message.from_user.id,
        )
        target_lang = await get_user_language(session, tg_id)

    await message.answer(tr("user_banned", lang, tg_id=tg_id))
    await message.bot.send_message(tg_id, tr("user_banned_notify", target_lang, reason=reason))


@router.message(Command("unban"))
async def admin_unban(message: Message, settings: Settings) -> None:
    if message.from_user is None:
        return
    async with session_scope() as session:
        lang = await get_user_language(session, message.from_user.id)
        if not _is_admin(message, settings):
            await message.answer(tr("admin_only", lang))
            return

        parts = (message.text or "").split(maxsplit=1)
        if len(parts) < 2 or not parts[1].isdigit():
            await message.answer(tr("usage_unban", lang))
            return

        tg_id = int(parts[1])
        user = await get_user_by_tg_id(session, tg_id)
        if user is None:
            await message.answer(tr("user_not_found", lang))
            return
        user.is_banned = False

    await message.answer(tr("user_unbanned", lang, tg_id=tg_id))


@router.message(Command("resolve"))
async def admin_resolve(message: Message, bot: Bot, settings: Settings) -> None:
    if message.from_user is None:
        return
    async with session_scope() as session:
        lang = await get_user_language(session, message.from_user.id)
        if not _is_admin(message, settings):
            await message.answer(tr("admin_only", lang))
            return

        parts = (message.text or "").split(maxsplit=2)
        if len(parts) < 3 or not parts[1].isdigit() or parts[2] not in {"refund", "release"}:
            await message.answer(tr("usage_resolve", lang))
            return

        order_id = int(parts[1])
        decision = parts[2]

        order = await get_order_by_id(session, order_id)
        if order is None:
            await message.answer(tr("order_not_found", lang))
            return

        customer_tg = order.customer.tg_id
        artist_tg = order.artist.tg_id
        customer_lang = await get_user_language(session, customer_tg)
        artist_lang = await get_user_language(session, artist_tg)

        if decision == "refund":
            order.status = OrderStatus.CANCELLED
            order.status_before_dispute = None
            customer_msg = tr("admin_refund_customer", customer_lang, order_id=order_id)
            artist_msg = tr("admin_refund_artist", artist_lang, order_id=order_id)
        else:
            order.status = OrderStatus.COMPLETED
            order.status_before_dispute = None
            commission = calculate_commission(
                order.price_rub,
                is_premium_active(order.artist.premium_until),
                order.commission_pct,
            )
            payout = max(order.price_rub - commission, 0)
            customer_msg = tr("admin_release_customer", customer_lang, order_id=order_id, payout=payout)
            artist_msg = tr("admin_release_artist", artist_lang, order_id=order_id, payout=payout)

    await message.answer(tr("admin_resolve_done", lang, order_id=order_id, decision=decision))
    await bot.send_message(customer_tg, customer_msg)
    await bot.send_message(artist_tg, artist_msg)
