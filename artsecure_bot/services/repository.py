from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Select, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from artsecure_bot.models import (
    BlacklistEntry,
    ArtAsset,
    EscrowEvent,
    EscrowInvoice,
    Order,
    OrderStatus,
    PaymentStatus,
    Portfolio,
    Report,
    User,
    UserLocale,
    UserRole,
)


async def get_user_by_tg_id(session: AsyncSession, tg_id: int) -> User | None:
    query = select(User).where(User.tg_id == tg_id)
    return await session.scalar(query)


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    query = select(User).where(User.id == user_id)
    return await session.scalar(query)


async def get_user_language(session: AsyncSession, tg_id: int) -> str:
    query = select(UserLocale).where(UserLocale.tg_id == tg_id)
    locale = await session.scalar(query)
    if locale is None:
        return "ru"
    return locale.language


async def set_user_language(session: AsyncSession, tg_id: int, language: str) -> None:
    query = select(UserLocale).where(UserLocale.tg_id == tg_id)
    locale = await session.scalar(query)
    if locale is None:
        locale = UserLocale(tg_id=tg_id, language=language)
        session.add(locale)
    else:
        locale.language = language
    await session.flush()


async def get_user_by_username(session: AsyncSession, username: str) -> User | None:
    normalized = username.lstrip("@").lower()
    query = select(User).where(func.lower(User.username) == normalized)
    return await session.scalar(query)


async def upsert_user(
    session: AsyncSession,
    tg_id: int,
    username: str | None,
    role: UserRole,
    nickname: str,
    contact: str,
) -> User:
    user = await get_user_by_tg_id(session, tg_id)
    if user is None:
        user = User(
            tg_id=tg_id,
            username=username,
            role=role,
            nickname=nickname,
            contact=contact,
        )
        session.add(user)
        await session.flush()
        return user

    user.username = username
    user.role = role
    user.nickname = nickname
    user.contact = contact
    await session.flush()
    return user


async def search_artists(session: AsyncSession, query_text: str) -> list[User]:
    query = (
        select(User)
        .where(User.role == UserRole.ARTIST)
        .where(
            (User.nickname.ilike(f"%{query_text}%"))
            | (User.username.ilike(f"%{query_text}%"))
            | (User.contact.ilike(f"%{query_text}%"))
        )
        .order_by(User.created_at.desc())
        .limit(15)
    )
    rows = await session.scalars(query)
    return list(rows)


async def get_next_available_artist(session: AsyncSession) -> User | None:
    """Get next available artist using round-robin strategy.

    Returns the artist who:
    - Has role ARTIST
    - Is not banned
    - Has is_available = True
    - Has profile_visible = True
    - Has the oldest last_offered_at (or NULL, which comes first)
    """
    query = (
        select(User)
        .where(User.role == UserRole.ARTIST)
        .where(User.is_banned == False)
        .where(User.is_available == True)
        .where(User.profile_visible == True)
        .order_by(User.last_offered_at.asc().nulls_first())
        .limit(1)
    )
    artist = await session.scalar(query)

    if artist is not None:
        # Update last_offered_at to mark this artist as recently offered
        artist.last_offered_at = datetime.now(timezone.utc)
        await session.flush()

    return artist


async def create_order(
    session: AsyncSession,
    customer_id: int,
    artist_id: int,
    title: str,
    details: str,
    price_rub: int,
    price_amount: str | None = None,
    price_currency: str = "RUB",
) -> Order:
    order = Order(
        customer_id=customer_id,
        artist_id=artist_id,
        title=title,
        details=details,
        price_rub=price_rub,
        price_amount=price_amount or str(price_rub),
        price_currency=price_currency,
        status=OrderStatus.PENDING_ARTIST,
    )
    session.add(order)
    await session.flush()
    return order


async def get_order_by_id(session: AsyncSession, order_id: int) -> Order | None:
    query: Select[tuple[Order]] = (
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.customer), selectinload(Order.artist), selectinload(Order.assets))
    )
    return await session.scalar(query)


async def list_orders_for_user(session: AsyncSession, user: User) -> list[Order]:
    query = select(Order).options(selectinload(Order.customer), selectinload(Order.artist))
    if user.role == UserRole.CUSTOMER:
        query = query.where(Order.customer_id == user.id)
    elif user.role == UserRole.ARTIST:
        query = query.where(Order.artist_id == user.id)
    else:
        query = query

    rows = await session.scalars(query.order_by(Order.created_at.desc()).limit(30))
    return list(rows)


async def list_disputed_orders(session: AsyncSession, limit: int = 50) -> list[Order]:
    query = (
        select(Order)
        .where(Order.status == OrderStatus.DISPUTED)
        .options(selectinload(Order.customer), selectinload(Order.artist), selectinload(Order.assets))
        .order_by(Order.created_at.desc())
        .limit(limit)
    )
    rows = await session.scalars(query)
    return list(rows)


async def has_orders_for_customer(session: AsyncSession, customer_id: int) -> bool:
    total = await session.scalar(select(func.count(Order.id)).where(Order.customer_id == customer_id)) or 0
    return int(total) > 0


async def has_orders_for_artist(session: AsyncSession, artist_id: int) -> bool:
    total = await session.scalar(select(func.count(Order.id)).where(Order.artist_id == artist_id)) or 0
    return int(total) > 0


async def has_send_art_available_orders(session: AsyncSession, artist_id: int) -> bool:
    total = await session.scalar(
        select(func.count(Order.id))
        .where(Order.artist_id == artist_id)
        .where(
            Order.status.in_(
                [
                    OrderStatus.IN_PROGRESS,
                    OrderStatus.PREVIEW_SENT,
                    OrderStatus.PAID_ESCROW,
                    OrderStatus.FINAL_REVIEW,
                ]
            )
        )
    ) or 0
    return int(total) > 0


async def create_report(
    session: AsyncSession,
    reporter_id: int,
    target_user_id: int,
    reason: str,
    order_id: int | None = None,
) -> Report:
    report = Report(
        reporter_id=reporter_id,
        target_user_id=target_user_id,
        order_id=order_id,
        reason=reason,
    )
    session.add(report)
    await session.flush()
    return report


async def list_reports(session: AsyncSession, limit: int = 100) -> list[Report]:
    query = select(Report).options(selectinload(Report.order)).order_by(Report.created_at.desc()).limit(limit)
    rows = await session.scalars(query)
    return list(rows)


async def list_users(session: AsyncSession, limit: int = 200) -> list[User]:
    query = select(User).order_by(User.created_at.desc()).limit(limit)
    rows = await session.scalars(query)
    return list(rows)


async def get_latest_open_invoice_for_order(session: AsyncSession, order_id: int) -> EscrowInvoice | None:
    query = (
        select(EscrowInvoice)
        .where(EscrowInvoice.order_id == order_id)
        .where(EscrowInvoice.status.in_([PaymentStatus.CREATED, PaymentStatus.AWAITING_PAYMENT]))
        .order_by(EscrowInvoice.created_at.desc())
        .limit(1)
    )
    return await session.scalar(query)


async def get_latest_invoice_for_order(session: AsyncSession, order_id: int) -> EscrowInvoice | None:
    query = (
        select(EscrowInvoice)
        .where(EscrowInvoice.order_id == order_id)
        .order_by(EscrowInvoice.created_at.desc())
        .limit(1)
    )
    return await session.scalar(query)


async def get_latest_confirmed_invoice_for_order(session: AsyncSession, order_id: int) -> EscrowInvoice | None:
    query = (
        select(EscrowInvoice)
        .where(EscrowInvoice.order_id == order_id)
        .where(EscrowInvoice.status == PaymentStatus.CONFIRMED)
        .order_by(EscrowInvoice.created_at.desc())
        .limit(1)
    )
    return await session.scalar(query)


async def get_invoice_by_id(session: AsyncSession, invoice_id: int) -> EscrowInvoice | None:
    query = select(EscrowInvoice).where(EscrowInvoice.id == invoice_id)
    return await session.scalar(query)


async def list_invoice_events(session: AsyncSession, invoice_id: int, limit: int = 30) -> list[EscrowEvent]:
    query = (
        select(EscrowEvent)
        .where(EscrowEvent.invoice_id == invoice_id)
        .order_by(EscrowEvent.created_at.desc())
        .limit(limit)
    )
    rows = await session.scalars(query)
    return list(rows)


async def delete_order_with_related(session: AsyncSession, order_id: int) -> None:
    invoice_ids = await session.scalars(select(EscrowInvoice.id).where(EscrowInvoice.order_id == order_id))
    invoice_id_list = list(invoice_ids)
    if invoice_id_list:
        await session.execute(delete(EscrowEvent).where(EscrowEvent.invoice_id.in_(invoice_id_list)))
    await session.execute(delete(EscrowInvoice).where(EscrowInvoice.order_id == order_id))
    await session.execute(delete(ArtAsset).where(ArtAsset.order_id == order_id))
    await session.execute(delete(Report).where(Report.order_id == order_id))
    await session.execute(delete(Order).where(Order.id == order_id))
    await session.flush()


async def add_to_blacklist(
    session: AsyncSession,
    user_id: int,
    reason: str,
    created_by_tg_id: int,
) -> BlacklistEntry:
    query = select(BlacklistEntry).where(BlacklistEntry.user_id == user_id)
    existing = await session.scalar(query)
    if existing is not None:
        existing.reason = reason
        existing.created_by_tg_id = created_by_tg_id
        await session.flush()
        return existing

    item = BlacklistEntry(user_id=user_id, reason=reason, created_by_tg_id=created_by_tg_id)
    session.add(item)
    await session.flush()
    return item


async def get_stats(session: AsyncSession) -> dict[str, int]:
    total_orders = await session.scalar(select(func.count(Order.id))) or 0
    completed_orders = await session.scalar(
        select(func.count(Order.id)).where(Order.status == OrderStatus.COMPLETED)
    ) or 0
    disputed_orders = await session.scalar(
        select(func.count(Order.id)).where(Order.status == OrderStatus.DISPUTED)
    ) or 0
    gross = await session.scalar(select(func.coalesce(func.sum(Order.price_rub), 0))) or 0

    return {
        "total_orders": int(total_orders),
        "completed_orders": int(completed_orders),
        "disputed_orders": int(disputed_orders),
        "gross_rub": int(gross),
    }


async def get_portfolio_items(session: AsyncSession, artist_id: int) -> list[Portfolio]:
    """Get all portfolio items for an artist, ordered by display_order."""
    query = (
        select(Portfolio)
        .where(Portfolio.artist_id == artist_id)
        .order_by(Portfolio.display_order.asc(), Portfolio.created_at.desc())
    )
    rows = await session.scalars(query)
    return list(rows)


async def count_completed_orders_for_user(session: AsyncSession, user_id: int, role: UserRole) -> int:
    """Count completed orders for a user, using an explicit query instead of
    lazy-loading the `customer_orders`/`artist_orders` relationships (which
    raises MissingGreenlet under AsyncSession when accessed outside of a
    selectinload/eager context)."""
    column = Order.artist_id if role == UserRole.ARTIST else Order.customer_id
    total = await session.scalar(
        select(func.count(Order.id)).where(column == user_id).where(Order.status == OrderStatus.COMPLETED)
    ) or 0
    return int(total)


async def update_user_profile(
    session: AsyncSession,
    user: User,
    *,
    nickname: str | None = None,
    bio: str | None = ...,
) -> User:
    """Update editable profile fields. `bio=None` clears it; omit (default `...`) to leave unchanged."""
    if nickname is not None:
        user.nickname = nickname
    if bio is not ...:
        user.bio = bio
    await session.flush()
    return user


async def create_portfolio_item(
    session: AsyncSession,
    artist_id: int,
    title: str,
    description: str | None = None,
    image_path: str | None = None,
    file_id: str | None = None,
) -> Portfolio:
    max_order = await session.scalar(
        select(func.max(Portfolio.display_order)).where(Portfolio.artist_id == artist_id)
    )
    next_order = (max_order + 1) if max_order is not None else 0
    item = Portfolio(
        artist_id=artist_id,
        title=title,
        description=description,
        image_path=image_path,
        file_id=file_id,
        display_order=next_order,
    )
    session.add(item)
    await session.flush()
    return item


async def get_portfolio_item_by_id(session: AsyncSession, item_id: int) -> Portfolio | None:
    query = select(Portfolio).where(Portfolio.id == item_id)
    return await session.scalar(query)


async def update_portfolio_item(
    session: AsyncSession,
    item: Portfolio,
    *,
    title: str | None = None,
    description: str | None = ...,
) -> Portfolio:
    if title is not None:
        item.title = title
    if description is not ...:
        item.description = description
    await session.flush()
    return item


async def delete_portfolio_item(session: AsyncSession, item: Portfolio) -> None:
    await session.delete(item)
    await session.flush()


async def reorder_portfolio_item(session: AsyncSession, item: Portfolio, new_order: int) -> None:
    item.display_order = new_order
    await session.flush()
