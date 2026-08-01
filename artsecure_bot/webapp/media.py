from __future__ import annotations

import io
import uuid
from pathlib import Path

from PIL import Image

PORTFOLIO_DIR = Path(__file__).resolve().parents[1] / "assets" / "portfolio_uploads"
MAX_DIMENSION = 1600
JPEG_QUALITY = 88


def _ensure_artist_dir(artist_tg_id: int) -> Path:
    artist_dir = PORTFOLIO_DIR / str(artist_tg_id)
    artist_dir.mkdir(parents=True, exist_ok=True)
    return artist_dir


async def save_portfolio_image(artist_tg_id: int, field) -> str:
    """Read an aiohttp multipart image field, downscale it, and store it as JPEG.

    Returns a relative path (`"<artist_tg_id>/<uuid>.jpg"`) suitable for `media_url`.
    Raises `ValueError` if the payload isn't a readable image.
    """
    data = await field.read(decode=False)
    if not data:
        raise ValueError("empty file")

    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except Exception as exc:
        raise ValueError("invalid image") from exc

    image = image.convert("RGB")
    image.thumbnail((MAX_DIMENSION, MAX_DIMENSION))

    artist_dir = _ensure_artist_dir(artist_tg_id)
    filename = f"{uuid.uuid4().hex}.jpg"
    dest = artist_dir / filename
    image.save(dest, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return f"{artist_tg_id}/{filename}"


def delete_portfolio_image(image_path: str) -> None:
    if not image_path:
        return
    root = PORTFOLIO_DIR.resolve()
    full = (PORTFOLIO_DIR / image_path).resolve()
    if root not in full.parents:
        return
    full.unlink(missing_ok=True)


def media_url(image_path: str) -> str:
    return f"/media/portfolio/{image_path}"


async def proxy_telegram_file(bot, file_id: str) -> bytes:
    """Download a Telegram-hosted file (used for legacy file_id-based portfolio items)."""
    file = await bot.get_file(file_id)
    buffer = io.BytesIO()
    await bot.download_file(file.file_path, destination=buffer)
    return buffer.getvalue()
