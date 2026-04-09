from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from artsecure_bot.config import Settings, load_settings
from artsecure_bot.db import init_db
from artsecure_bot.handlers import admin, art, chat, common, nda, orders, payments, report, search
from artsecure_bot.middlewares.rate_limit import RateLimitMiddleware


async def run_bot(settings: Settings) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    await init_db(settings.database_url)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    limiter = RateLimitMiddleware(settings.rate_limit_seconds)
    dp.message.middleware(limiter)
    dp.callback_query.middleware(limiter)

    dp["settings"] = settings

    dp.include_routers(
        common.router,
        orders.router,
        art.router,
        search.router,
        report.router,
        payments.router,
        nda.router,
        chat.router,
        admin.router,
    )

    await dp.start_polling(bot)


def run() -> None:
    settings = load_settings()
    asyncio.run(run_bot(settings))


if __name__ == "__main__":
    run()
