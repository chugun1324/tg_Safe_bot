from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from artsecure_bot.models import Base

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


async def init_db(database_url: str) -> None:
    global _engine, _session_factory
    engine_kwargs = {"future": True}
    if database_url.startswith("sqlite"):
        engine_kwargs["connect_args"] = {"timeout": 30}
    _engine = create_async_engine(database_url, **engine_kwargs)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)

    async with _engine.begin() as conn:
        if database_url.startswith("sqlite"):
            await conn.execute(text("PRAGMA journal_mode=WAL"))
            await conn.execute(text("PRAGMA synchronous=NORMAL"))
            await conn.execute(text("PRAGMA busy_timeout=30000"))
        await conn.run_sync(Base.metadata.create_all)
        try:
            result = await conn.execute(text("PRAGMA table_info(orders)"))
            columns = {row[1] for row in result.fetchall()}
            if "customer_done" not in columns:
                await conn.execute(text("ALTER TABLE orders ADD COLUMN customer_done BOOLEAN DEFAULT 0"))
            if "artist_done" not in columns:
                await conn.execute(text("ALTER TABLE orders ADD COLUMN artist_done BOOLEAN DEFAULT 0"))
            if "review_deadline_at" not in columns:
                await conn.execute(text("ALTER TABLE orders ADD COLUMN review_deadline_at DATETIME"))
            if "status_before_dispute" not in columns:
                await conn.execute(text("ALTER TABLE orders ADD COLUMN status_before_dispute VARCHAR(32)"))
            if "dispute_reason" not in columns:
                await conn.execute(text("ALTER TABLE orders ADD COLUMN dispute_reason VARCHAR(64)"))
            if "price_currency" not in columns:
                await conn.execute(text("ALTER TABLE orders ADD COLUMN price_currency VARCHAR(8) DEFAULT 'RUB'"))
            if "price_amount" not in columns:
                await conn.execute(text("ALTER TABLE orders ADD COLUMN price_amount VARCHAR(32) DEFAULT '0'"))

            users_result = await conn.execute(text("PRAGMA table_info(users)"))
            users_columns = {row[1] for row in users_result.fetchall()}
            if "wallet_address" not in users_columns:
                await conn.execute(text("ALTER TABLE users ADD COLUMN wallet_address VARCHAR(128)"))

            invoice_result = await conn.execute(text("PRAGMA table_info(escrow_invoices)"))
            invoice_columns = {row[1] for row in invoice_result.fetchall()}
            if "payer_wallet_address" not in invoice_columns:
                await conn.execute(text("ALTER TABLE escrow_invoices ADD COLUMN payer_wallet_address VARCHAR(128)"))
        except Exception:
            # Non-SQLite engines should be migrated separately.
            pass


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("Database is not initialized")

    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
