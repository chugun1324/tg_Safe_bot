from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from artsecure_bot.config import Settings
from artsecure_bot.db import session_scope
from artsecure_bot.handlers.utils import build_main_menu_for_user, require_registered_user
from artsecure_bot.i18n import tr, variants
from artsecure_bot.keyboards import open_profile_webapp_button, with_extra_row
from artsecure_bot.models import UserRole
from artsecure_bot.services.repository import (
    count_completed_orders_for_user,
    get_portfolio_items,
    get_user_by_tg_id,
    get_user_by_username,
    get_user_language,
)
from artsecure_bot.states import EditProfileState

router = Router()


def _availability_keyboard(is_available: bool, language: str) -> InlineKeyboardMarkup:
    """Create keyboard for toggling artist availability."""
    if is_available:
        btn_text = tr("btn_set_unavailable", language)
        callback = "set_availability:off"
    else:
        btn_text = tr("btn_set_available", language)
        callback = "set_availability:on"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=btn_text, callback_data=callback)],
            [InlineKeyboardButton(text=tr("btn_edit_profile", language), callback_data="edit_profile")],
        ]
    )


def _profile_visibility_keyboard(is_visible: bool, language: str) -> InlineKeyboardMarkup:
    """Create keyboard for toggling profile visibility in automatic search."""
    if is_visible:
        btn_text = tr("btn_hide_profile", language)
        callback = "profile_visibility:hide"
    else:
        btn_text = tr("btn_show_profile", language)
        callback = "profile_visibility:show"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=btn_text, callback_data=callback)],
        ]
    )


def _profile_view_keyboard(
    user_tg_id: int,
    user_role: UserRole,
    language: str,
    viewer_role: UserRole | None = None,
    miniapp_url: str = "",
) -> InlineKeyboardMarkup | None:
    """Create keyboard for viewing another user's profile."""
    buttons = []

    # If viewing an artist profile and viewer is a customer, show "Create Order" button
    if user_role == UserRole.ARTIST and viewer_role == UserRole.CUSTOMER:
        buttons.append([InlineKeyboardButton(
            text=tr("btn_create_order_with_artist", language),
            callback_data=f"create_order_with:{user_tg_id}"
        )])

    # Show portfolio button for artists
    if user_role == UserRole.ARTIST:
        buttons.append([InlineKeyboardButton(
            text=tr("btn_view_portfolio", language),
            callback_data=f"view_portfolio:{user_tg_id}"
        )])

    markup = InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None
    open_profile_button = open_profile_webapp_button(user_tg_id, miniapp_url, language)
    return with_extra_row(markup, open_profile_button)


def _format_profile_text(
    user,
    language: str,
    *,
    completed_as_customer: int = 0,
    completed_as_artist: int = 0,
) -> str:
    """Format profile information text."""
    role_label = tr(f"role_{user.role.value}", language)
    username_display = f"@{user.username}" if user.username else tr("no_username", language)

    lines = [
        tr("profile_header", language, username=username_display),
        "",
        f"👤 {tr('profile_nickname', language)}: {user.nickname}",
        f"🎭 {tr('profile_role', language)}: {role_label}",
    ]

    if user.bio:
        lines.append(f"📝 {tr('profile_bio', language)}: {user.bio}")

    lines.append(f"📅 {tr('profile_registered', language)}: {user.created_at.strftime('%Y-%m-%d')}")

    if user.role == UserRole.ARTIST:
        availability_status = tr("profile_available", language) if user.is_available else tr("profile_unavailable", language)
        lines.append(f"🟢 {tr('profile_status', language)}: {availability_status}")
        lines.append(f"✅ {tr('profile_completed_orders', language)}: {completed_as_artist}")
        if user.rating > 0:
            lines.append(f"⭐ {tr('profile_rating', language)}: {user.rating}/100")
    elif user.role == UserRole.CUSTOMER:
        lines.append(f"✅ {tr('profile_completed_orders', language)}: {completed_as_customer}")

    if user.wallet_address:
        wallet_short = f"{user.wallet_address[:6]}...{user.wallet_address[-4:]}"
        lines.append(f"💼 {tr('profile_wallet', language)}: {wallet_short}")

    return "\n".join(lines)


@router.message(Command("profile"))
@router.message(F.text.in_(variants("btn_profile")))
async def show_own_profile(message: Message, settings: Settings) -> None:
    """Show user's own profile."""
    async with session_scope() as session:
        user = await require_registered_user(message, session)
        if user is None:
            return

        lang = await get_user_language(session, user.tg_id)

        completed_as_customer = await count_completed_orders_for_user(session, user.id, UserRole.CUSTOMER)
        completed_as_artist = await count_completed_orders_for_user(session, user.id, UserRole.ARTIST)

        portfolio_items = await get_portfolio_items(session, user.id) if user.role == UserRole.ARTIST else []
        is_empty = user.role == UserRole.ARTIST and not user.bio and not portfolio_items

        profile_text = _format_profile_text(
            user,
            lang,
            completed_as_customer=completed_as_customer,
            completed_as_artist=completed_as_artist,
        )

        # Show availability and visibility controls for artists
        if user.role == UserRole.ARTIST:
            keyboard = _availability_keyboard(user.is_available, lang)
            visibility_status = tr("profile_status_visible", lang) if user.profile_visible else tr("profile_status_hidden", lang)
            profile_text += f"\n\n🔍 {visibility_status}"
        else:
            keyboard = None

        role = user.role
        tg_id = user.tg_id
        profile_visible = user.profile_visible

    open_button = open_profile_webapp_button(tg_id, settings.miniapp_url, lang)

    if is_empty and open_button:
        await message.answer(
            tr("profile_empty_owner_prompt", lang, btn_open_profile=tr("btn_open_profile", lang)),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[open_button]]),
        )

    await message.answer(profile_text, reply_markup=keyboard)

    # Show visibility toggle for artists
    if role == UserRole.ARTIST:
        visibility_keyboard = _profile_visibility_keyboard(profile_visible, lang)
        await message.answer(
            tr("profile_management_title", lang),
            reply_markup=visibility_keyboard if is_empty else with_extra_row(visibility_keyboard, open_button),
        )
    elif open_button:
        await message.answer(
            tr("btn_open_profile", lang),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[open_button]]),
        )


@router.message(Command("view_profile"))
async def view_profile_command(message: Message, settings: Settings) -> None:
    """View another user's profile by username: /view_profile @username"""
    if message.from_user is None:
        return

    async with session_scope() as session:
        lang = await get_user_language(session, message.from_user.id)
        viewer = await get_user_by_tg_id(session, message.from_user.id)

        parts = (message.text or "").split(maxsplit=1)
        if len(parts) < 2:
            await message.answer(tr("usage_view_profile", lang))
            return

        username = parts[1].strip().lstrip("@")
        target_user = await get_user_by_username(session, username)

        if target_user is None:
            await message.answer(tr("user_not_found", lang))
            return

        completed_as_customer = await count_completed_orders_for_user(session, target_user.id, UserRole.CUSTOMER)
        completed_as_artist = await count_completed_orders_for_user(session, target_user.id, UserRole.ARTIST)

        profile_text = _format_profile_text(
            target_user,
            lang,
            completed_as_customer=completed_as_customer,
            completed_as_artist=completed_as_artist,
        )

        keyboard = _profile_view_keyboard(
            target_user.tg_id,
            target_user.role,
            lang,
            viewer.role if viewer else None,
            miniapp_url=settings.miniapp_url,
        )

    await message.answer(profile_text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("set_availability:"))
async def toggle_availability(callback: CallbackQuery) -> None:
    """Toggle artist availability status."""
    if callback.from_user is None or callback.data is None:
        return

    new_status = callback.data.split(":")[1] == "on"

    async with session_scope() as session:
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if user is None:
            lang = await get_user_language(session, callback.from_user.id)
            await callback.answer(tr("err_not_registered", lang), show_alert=True)
            return

        lang = await get_user_language(session, user.tg_id)

        if user.role != UserRole.ARTIST:
            await callback.answer(tr("availability_only_artist", lang), show_alert=True)
            return

        user.is_available = new_status
        await session.commit()

        status_text = tr("profile_available", lang) if new_status else tr("profile_unavailable", lang)
        await callback.answer(tr("availability_updated", lang, status=status_text))

        completed_as_artist = await count_completed_orders_for_user(session, user.id, UserRole.ARTIST)
        profile_text = _format_profile_text(user, lang, completed_as_artist=completed_as_artist)

    if callback.message:
        await callback.message.edit_text(
            profile_text,
            reply_markup=_availability_keyboard(new_status, lang),
        )


@router.callback_query(F.data == "edit_profile")
async def edit_profile_start(callback: CallbackQuery, state: FSMContext) -> None:
    """Start profile editing flow."""
    if callback.from_user is None:
        return

    async with session_scope() as session:
        lang = await get_user_language(session, callback.from_user.id)

    await callback.answer()
    await state.set_state(EditProfileState.waiting_bio)
    if callback.message:
        await callback.message.answer(tr("edit_profile_bio_prompt", lang))


@router.message(EditProfileState.waiting_bio)
async def edit_profile_bio(message: Message, state: FSMContext) -> None:
    """Update user bio."""
    if message.from_user is None:
        return

    bio_text = (message.text or "").strip()

    async with session_scope() as session:
        user = await get_user_by_tg_id(session, message.from_user.id)
        lang = await get_user_language(session, message.from_user.id)

        if user is None:
            await message.answer(tr("err_not_registered", lang))
            await state.clear()
            return

        if len(bio_text) > 500:
            await message.answer(tr("edit_profile_bio_too_long", lang))
            return

        user.bio = bio_text if bio_text else None
        await session.commit()

        menu = await build_main_menu_for_user(session, user)

    await state.clear()
    await message.answer(tr("edit_profile_bio_saved", lang), reply_markup=menu)


@router.callback_query(F.data.startswith("view_portfolio:"))
async def view_portfolio_callback(callback: CallbackQuery) -> None:
    """Show artist portfolio."""
    if callback.from_user is None or callback.data is None:
        return

    parts = callback.data.split(":")
    if len(parts) != 2 or not parts[1].isdigit():
        await callback.answer()
        return

    artist_tg_id = int(parts[1])

    async with session_scope() as session:
        lang = await get_user_language(session, callback.from_user.id)
        artist = await get_user_by_tg_id(session, artist_tg_id)

        if artist is None or artist.role != UserRole.ARTIST:
            await callback.answer(tr("user_not_found", lang), show_alert=True)
            return

        portfolio_items = await get_portfolio_items(session, artist.id)

    if not portfolio_items:
        await callback.answer(tr("portfolio_empty", lang), show_alert=True)
        return

    await callback.answer()

    # Send portfolio items
    for item in portfolio_items[:10]:  # Limit to 10 items
        caption = f"📌 {item.title}"
        if item.description:
            caption += f"\n\n{item.description}"

        if item.file_id and callback.message:
            try:
                await callback.message.bot.send_photo(
                    chat_id=callback.message.chat.id,
                    photo=item.file_id,
                    caption=caption
                )
            except Exception:
                # If file_id is invalid, just send text
                await callback.message.answer(caption)


@router.callback_query(F.data.startswith("create_order_with:"))
async def create_order_with_artist_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Start order creation with specific artist."""
    if callback.from_user is None or callback.data is None or callback.message is None:
        return

    parts = callback.data.split(":")
    if len(parts) != 2 or not parts[1].isdigit():
        await callback.answer()
        return

    artist_tg_id = int(parts[1])

    async with session_scope() as session:
        lang = await get_user_language(session, callback.from_user.id)
        viewer = await get_user_by_tg_id(session, callback.from_user.id)

        if viewer is None:
            await callback.answer(tr("err_not_registered", lang), show_alert=True)
            return

        if viewer.role != UserRole.CUSTOMER:
            await callback.answer(tr("create_only_customer", lang), show_alert=True)
            return

        if not viewer.wallet_address:
            await callback.message.answer(tr("wallet_required_before_orders", lang, btn_wallet=tr("btn_wallet", lang)))
            await callback.answer()
            return

        artist = await get_user_by_tg_id(session, artist_tg_id)

        if artist is None or artist.role != UserRole.ARTIST:
            await callback.answer(tr("user_not_found", lang), show_alert=True)
            return

        # Store artist info and start order creation flow
        await state.clear()
        await state.update_data(artist_tg_id=artist.tg_id, artist_username=artist.username or str(artist.tg_id))
        await state.set_state(EditProfileState.waiting_bio)  # Will use CreateOrderState in next import fix

    await callback.answer()

    # Import order keyboard here to avoid circular import
    from artsecure_bot.keyboards import order_currency_keyboard
    from artsecure_bot.states import CreateOrderState

    await state.set_state(CreateOrderState.waiting_currency)
    await callback.message.answer(tr("create_ask_currency", lang), reply_markup=order_currency_keyboard(lang))


@router.callback_query(F.data.startswith("profile_visibility:"))
async def toggle_profile_visibility(callback: CallbackQuery) -> None:
    """Toggle artist profile visibility in automatic search."""
    if callback.from_user is None or callback.data is None:
        return

    new_visibility = callback.data.split(":")[1] == "show"

    async with session_scope() as session:
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if user is None:
            lang = await get_user_language(session, callback.from_user.id)
            await callback.answer(tr("err_not_registered", lang), show_alert=True)
            return

        lang = await get_user_language(session, user.tg_id)

        if user.role != UserRole.ARTIST:
            await callback.answer(tr("err_wrong_role", lang), show_alert=True)
            return

        user.profile_visible = new_visibility
        await session.commit()

        status_text = tr("profile_status_visible", lang) if new_visibility else tr("profile_status_hidden", lang)
        await callback.answer(tr("profile_visibility_updated", lang))

    if callback.message:
        await callback.message.edit_text(
            f"{tr('profile_management_title', lang)}\n\n{status_text}",
            reply_markup=_profile_visibility_keyboard(new_visibility, lang),
        )
