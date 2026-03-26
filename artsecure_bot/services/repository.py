from __future__ import annotations

from sqlalchemy import Select, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from artsecure_bot.models import (
    BlacklistEntry,
    ArtAsset,
    Order,
    OrderStatus,
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


async def create_order(
    session: AsyncSession,
    customer_id: int,
    artist_id: int,
    title: str,
    details: str,
    price_rub: int,
) -> Order:
    order = Order(
        customer_id=customer_id,
        artist_id=artist_id,
        title=title,
        details=details,
        price_rub=price_rub,
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


async def delete_order_with_related(session: AsyncSession, order_id: int) -> None:
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
