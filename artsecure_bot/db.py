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
    _engine = create_async_engine(database_url, future=True)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        try:
            result = await conn.execute(text("PRAGMA table_info(orders)"))
            columns = {row[1] for row in result.fetchall()}
            if "customer_done" not in columns:
                await conn.execute(text("ALTER TABLE orders ADD COLUMN customer_done BOOLEAN DEFAULT 0"))
            if "artist_done" not in columns:
                await conn.execute(text("ALTER TABLE orders ADD COLUMN artist_done BOOLEAN DEFAULT 0"))
            if "status_before_dispute" not in columns:
                await conn.execute(text("ALTER TABLE orders ADD COLUMN status_before_dispute VARCHAR(32)"))
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
