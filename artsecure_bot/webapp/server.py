from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from aiohttp import web

from artsecure_bot.config import Settings
from artsecure_bot.webapp.auth import telegram_auth_middleware
from artsecure_bot.webapp.debug import debug_init, debug_page
from artsecure_bot.webapp.media import PORTFOLIO_DIR
from artsecure_bot.webapp.routes.profile import register_profile_routes

logger = logging.getLogger(__name__)

# The mini app's production build (miniapp/dist), served directly so the
# tunnel only has to point at one process/port. Vite's own dev server works
# fine in a plain browser but its HMR websocket client hangs indefinitely
# inside Telegram Desktop's embedded WebView — serve the static build instead
# for anything that has to load through an actual Telegram client.
MINIAPP_DIST_DIR = Path(__file__).resolve().parents[2] / "miniapp" / "dist"

CORS_HEADERS = {
    "Access-Control-Allow-Headers": "Content-Type, X-Telegram-Init-Data",
    "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
    "Access-Control-Max-Age": "86400",
}


@web.middleware
async def cors_middleware(request: web.Request, handler):
    origin = request.headers.get("Origin", "*")

    if request.method == "OPTIONS":
        response = web.Response(status=204)
    else:
        try:
            response = await handler(request)
        except web.HTTPException as exc:
            response = exc

    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers.update(CORS_HEADERS)
    return response


async def _preflight(_request: web.Request) -> web.Response:
    return web.Response(status=204)


def build_app(bot, settings: Settings) -> web.Application:
    app = web.Application(middlewares=[cors_middleware, telegram_auth_middleware], client_max_size=15 * 1024 * 1024)
    app["bot"] = bot
    app["bot_token"] = settings.bot_token

    register_profile_routes(app)
    app.router.add_route("OPTIONS", "/{tail:.*}", _preflight)
    app.router.add_get("/debug", debug_page)
    app.router.add_get("/debug-init", debug_init)

    PORTFOLIO_DIR.mkdir(parents=True, exist_ok=True)
    app.router.add_static("/media/portfolio/", path=str(PORTFOLIO_DIR), name="portfolio_media", show_index=False)

    if MINIAPP_DIST_DIR.exists():
        assets_dir = MINIAPP_DIST_DIR / "assets"
        if assets_dir.exists():
            app.router.add_static("/assets/", path=str(assets_dir), name="miniapp_assets")

        async def _dist_file(request: web.Request) -> web.FileResponse:
            return web.FileResponse(MINIAPP_DIST_DIR / request.match_info["name"])

        async def _index(_request: web.Request) -> web.FileResponse:
            return web.FileResponse(MINIAPP_DIST_DIR / "index.html")

        app.router.add_get("/", _index)
        app.router.add_get(r"/{name:favicon\.svg|icons\.svg}", _dist_file)
    else:
        logger.warning(
            "miniapp/dist not found — build it with `cd miniapp && npm run build`; "
            "mini app static assets won't be served."
        )

    return app


async def run_webapp(bot, settings: Settings) -> None:
    if not settings.miniapp_url:
        logger.warning("MINIAPP_URL is not set — mini app open buttons will be hidden, but the API server still starts.")

    app = build_app(bot, settings)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, settings.webapp_host, settings.webapp_port)
    await site.start()
    logger.info("Mini app API server listening on %s:%s", settings.webapp_host, settings.webapp_port)

    try:
        # Keep the task alive until cancelled by the caller.
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()
