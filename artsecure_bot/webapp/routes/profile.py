from __future__ import annotations

import logging

from aiohttp import web

from artsecure_bot.db import session_scope
from artsecure_bot.models import Portfolio, User, UserRole
from artsecure_bot.services.repository import (
    count_completed_orders_for_user,
    create_portfolio_item,
    delete_portfolio_item,
    get_portfolio_item_by_id,
    get_portfolio_items,
    get_user_by_tg_id,
    reorder_portfolio_item,
    update_portfolio_item,
    update_user_profile,
)
from artsecure_bot.webapp.media import delete_portfolio_image, media_url, proxy_telegram_file, save_portfolio_image

logger = logging.getLogger(__name__)

MAX_BIO_LEN = 500
MAX_NICKNAME_LEN = 64
MAX_TITLE_LEN = 255
MAX_DESCRIPTION_LEN = 1000


def _portfolio_item_dict(item: Portfolio) -> dict:
    if item.image_path:
        file_url: str | None = media_url(item.image_path)
    elif item.file_id:
        file_url = f"/api/tg-file/{item.file_id}"
    else:
        file_url = None

    return {
        "id": item.id,
        "artist_id": item.artist_id,
        "title": item.title,
        "description": item.description,
        "display_order": item.display_order,
        "file_id": item.file_id,
        "file_url": file_url,
        "created_at": item.created_at.isoformat(),
    }


def _user_dict(user: User, *, completed_orders_count: int) -> dict:
    return {
        "id": user.id,
        "tg_id": user.tg_id,
        "username": user.username,
        "nickname": user.nickname,
        "role": user.role.value,
        "bio": user.bio,
        "completed_orders_count": completed_orders_count,
        "rating": user.rating,
        "is_available": user.is_available,
        "profile_visible": user.profile_visible,
        "created_at": user.created_at.isoformat(),
    }


async def get_profile(request: web.Request) -> web.Response:
    try:
        target_tg_id = int(request.match_info["tg_id"])
    except ValueError:
        return web.json_response({"error": "invalid_tg_id"}, status=400)

    viewer_tg_id: int = request["viewer_tg_id"]
    logger.info("get_profile: viewer=%s target=%s", viewer_tg_id, target_tg_id)

    async with session_scope() as session:
        user = await get_user_by_tg_id(session, target_tg_id)
        if user is None or user.role not in (UserRole.ARTIST, UserRole.CUSTOMER):
            logger.info(
                "get_profile: target=%s not found or wrong role (role=%s)",
                target_tg_id,
                user.role if user else None,
            )
            return web.json_response({"error": "not_found"}, status=404)

        completed = await count_completed_orders_for_user(session, user.id, user.role)

        portfolio_items: list[Portfolio] = []
        if user.role == UserRole.ARTIST:
            portfolio_items = await get_portfolio_items(session, user.id)

        return web.json_response(
            {
                "user": _user_dict(user, completed_orders_count=completed),
                "portfolio": [_portfolio_item_dict(item) for item in portfolio_items],
                "is_owner": viewer_tg_id == target_tg_id,
            }
        )


async def update_profile(request: web.Request) -> web.Response:
    viewer_tg_id: int = request["viewer_tg_id"]

    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"error": "invalid_json"}, status=400)

    nickname = payload.get("nickname")
    if nickname is not None:
        nickname = str(nickname).strip()
        if not (1 <= len(nickname) <= MAX_NICKNAME_LEN):
            return web.json_response({"error": "invalid_nickname"}, status=400)

    bio_provided = "bio" in payload
    bio = payload.get("bio")
    if bio_provided and bio is not None:
        bio = str(bio).strip()
        if len(bio) > MAX_BIO_LEN:
            return web.json_response({"error": "bio_too_long"}, status=400)
        bio = bio or None

    async with session_scope() as session:
        user = await get_user_by_tg_id(session, viewer_tg_id)
        if user is None:
            return web.json_response({"error": "not_found"}, status=404)

        user = await update_user_profile(
            session,
            user,
            nickname=nickname,
            bio=bio if bio_provided else ...,
        )
        completed = await count_completed_orders_for_user(session, user.id, user.role)
        return web.json_response(_user_dict(user, completed_orders_count=completed))


async def add_portfolio_item(request: web.Request) -> web.Response:
    viewer_tg_id: int = request["viewer_tg_id"]

    if not request.content_type or "multipart/form-data" not in request.content_type:
        return web.json_response({"error": "expected_multipart"}, status=400)

    async with session_scope() as session:
        user = await get_user_by_tg_id(session, viewer_tg_id)
        if user is None:
            return web.json_response({"error": "not_found"}, status=404)
        if user.role != UserRole.ARTIST:
            return web.json_response({"error": "not_artist"}, status=403)

        title = ""
        description: str | None = None
        image_path: str | None = None

        reader = await request.multipart()
        async for field in reader:
            if field.name == "title":
                title = (await field.text()).strip()
            elif field.name == "description":
                description = (await field.text()).strip() or None
            elif field.name == "image":
                try:
                    image_path = await save_portfolio_image(user.tg_id, field)
                except ValueError:
                    return web.json_response({"error": "invalid_image"}, status=400)

        if image_path is None:
            return web.json_response({"error": "image_required"}, status=400)

        title = (title or "Без названия")[:MAX_TITLE_LEN]
        if description:
            description = description[:MAX_DESCRIPTION_LEN]

        item = await create_portfolio_item(
            session,
            artist_id=user.id,
            title=title,
            description=description,
            image_path=image_path,
        )
        return web.json_response(_portfolio_item_dict(item), status=201)


async def _load_owned_portfolio_item(session, viewer_tg_id: int, item_id: int) -> Portfolio | None:
    user = await get_user_by_tg_id(session, viewer_tg_id)
    if user is None:
        return None
    item = await get_portfolio_item_by_id(session, item_id)
    if item is None or item.artist_id != user.id:
        return None
    return item


async def patch_portfolio_item(request: web.Request) -> web.Response:
    viewer_tg_id: int = request["viewer_tg_id"]
    try:
        item_id = int(request.match_info["item_id"])
    except ValueError:
        return web.json_response({"error": "invalid_id"}, status=400)

    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"error": "invalid_json"}, status=400)

    async with session_scope() as session:
        item = await _load_owned_portfolio_item(session, viewer_tg_id, item_id)
        if item is None:
            return web.json_response({"error": "not_found"}, status=404)

        title = payload.get("title")
        if title is not None:
            title = str(title).strip()[:MAX_TITLE_LEN] or item.title

        description_provided = "description" in payload
        description = payload.get("description")
        if description_provided and description is not None:
            description = str(description).strip()[:MAX_DESCRIPTION_LEN] or None

        item = await update_portfolio_item(
            session,
            item,
            title=title,
            description=description if description_provided else ...,
        )
        return web.json_response(_portfolio_item_dict(item))


async def delete_portfolio_item_route(request: web.Request) -> web.Response:
    viewer_tg_id: int = request["viewer_tg_id"]
    try:
        item_id = int(request.match_info["item_id"])
    except ValueError:
        return web.json_response({"error": "invalid_id"}, status=400)

    async with session_scope() as session:
        item = await _load_owned_portfolio_item(session, viewer_tg_id, item_id)
        if item is None:
            return web.json_response({"error": "not_found"}, status=404)
        image_path = item.image_path
        await delete_portfolio_item(session, item)

    if image_path:
        delete_portfolio_image(image_path)
    return web.json_response({"ok": True})


async def reorder_portfolio_item_route(request: web.Request) -> web.Response:
    viewer_tg_id: int = request["viewer_tg_id"]
    try:
        item_id = int(request.match_info["item_id"])
    except ValueError:
        return web.json_response({"error": "invalid_id"}, status=400)

    try:
        payload = await request.json()
        new_order = int(payload["display_order"])
    except Exception:
        return web.json_response({"error": "invalid_json"}, status=400)

    async with session_scope() as session:
        item = await _load_owned_portfolio_item(session, viewer_tg_id, item_id)
        if item is None:
            return web.json_response({"error": "not_found"}, status=404)
        await reorder_portfolio_item(session, item, new_order)

    return web.json_response({"ok": True})


async def get_tg_file(request: web.Request) -> web.Response:
    file_id = request.match_info["file_id"]
    bot = request.app["bot"]
    try:
        content = await proxy_telegram_file(bot, file_id)
    except Exception:
        return web.json_response({"error": "file_not_found"}, status=404)
    return web.Response(body=content, content_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})


def register_profile_routes(app: web.Application) -> None:
    app.router.add_get("/api/profile/{tg_id}", get_profile)
    app.router.add_put("/api/profile/me", update_profile)
    app.router.add_post("/api/portfolio", add_portfolio_item)
    app.router.add_patch("/api/portfolio/{item_id}", patch_portfolio_item)
    app.router.add_delete("/api/portfolio/{item_id}", delete_portfolio_item_route)
    app.router.add_patch("/api/portfolio/{item_id}/reorder", reorder_portfolio_item_route)
    app.router.add_get("/api/tg-file/{file_id}", get_tg_file)
