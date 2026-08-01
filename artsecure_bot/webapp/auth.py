from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from urllib.parse import parse_qsl

from aiohttp import web

logger = logging.getLogger(__name__)

INIT_DATA_HEADER = "X-Telegram-Init-Data"
MAX_INIT_DATA_AGE_SECONDS = 24 * 60 * 60

# Only /api/* needs a verified Telegram session — everything else (the mini
# app's static shell, media, the Telegram file proxy) must stay reachable
# without initData, since the frontend needs to load before it can send it.
_PUBLIC_API_PREFIXES = ("/api/tg-file/",)


def _requires_auth(path: str) -> bool:
    if not path.startswith("/api/"):
        return False
    return not path.startswith(_PUBLIC_API_PREFIXES)


def verify_init_data(init_data: str, bot_token: str) -> dict | None:
    """Validate Telegram WebApp initData per the documented HMAC-SHA256 algorithm.

    Returns the parsed `user` dict on success, `None` if missing/invalid/stale.
    """
    if not init_data or not bot_token:
        return None

    try:
        pairs = parse_qsl(init_data, strict_parsing=True, keep_blank_values=True)
    except ValueError:
        return None

    data = dict(pairs)
    received_hash = data.pop("hash", None)
    if not received_hash:
        return None

    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(data.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        logger.warning(
            "HMAC mismatch: computed=%s received=%s data_check_string=%r",
            computed_hash,
            received_hash,
            data_check_string,
        )
        return None

    auth_date_raw = data.get("auth_date")
    if auth_date_raw:
        try:
            auth_date = int(auth_date_raw)
        except ValueError:
            return None
        if time.time() - auth_date > MAX_INIT_DATA_AGE_SECONDS:
            return None

    user_raw = data.get("user")
    if not user_raw:
        return None
    try:
        user = json.loads(user_raw)
    except json.JSONDecodeError:
        return None

    if "id" not in user:
        return None
    return user


@web.middleware
async def telegram_auth_middleware(request: web.Request, handler):
    if request.method == "OPTIONS":
        return await handler(request)

    if not _requires_auth(request.path):
        return await handler(request)

    bot_token = request.app["bot_token"]
    init_data = request.headers.get(INIT_DATA_HEADER, "")
    user = verify_init_data(init_data, bot_token)
    if user is None:
        logger.warning("Rejected initData (len=%d): %r", len(init_data), init_data)
        return web.json_response({"error": "unauthorized"}, status=401)

    request["viewer_tg_id"] = int(user["id"])
    request["viewer_user"] = user
    return await handler(request)
