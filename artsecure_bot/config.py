from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    bot_token: str
    database_url: str
    admin_ids: set[int]
    support_chat_url: str
    news_channel: str
    rate_limit_seconds: float



def _parse_admin_ids(raw_value: str) -> set[int]:
    items = [item.strip() for item in raw_value.split(",") if item.strip()]
    return {int(item) for item in items}


def load_settings() -> Settings:
    load_dotenv()

    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        raise RuntimeError("BOT_TOKEN is required")

    database_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./artsecure.db").strip()
    support_chat_url = os.getenv("SUPPORT_CHAT_URL", "https://t.me/your_support").strip()
    news_channel = os.getenv("NEWS_CHANNEL", "@ArtSecureNews").strip()
    rate_limit_seconds = float(os.getenv("RATE_LIMIT_SECONDS", "1.0"))
    admin_ids = _parse_admin_ids(os.getenv("ADMIN_IDS", ""))

    return Settings(
        bot_token=bot_token,
        database_url=database_url,
        admin_ids=admin_ids,
        support_chat_url=support_chat_url,
        news_channel=news_channel,
        rate_limit_seconds=rate_limit_seconds,
    )
