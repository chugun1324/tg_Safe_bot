from __future__ import annotations

import io
import math
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont


def _load_font(font_size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype("DejaVuSans.ttf", font_size)
    except Exception:
        return ImageFont.load_default()


def add_text_watermark(image_bytes: bytes, order_id: int, artist_nick: str) -> bytes:
    image = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    watermark = f"ArtSecure | order #{order_id} | {artist_nick} | {datetime.now().strftime('%Y-%m-%d')}"

    diagonal = int(math.hypot(image.width, image.height))
    tile_size = max(diagonal, 1)
    font_size = max(16, min(image.width, image.height) // 18)
    font = _load_font(font_size)

    pattern = Image.new("RGBA", (tile_size, tile_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(pattern)
    bbox = draw.textbbox((0, 0), watermark, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    step_x = max(text_width + font_size * 2, 120)
    step_y = max(text_height + font_size * 2, 80)

    for y in range(-step_y, tile_size + step_y, step_y):
        for x in range(-step_x, tile_size + step_x, step_x):
            draw.text((x, y), watermark, fill=(255, 255, 255, 48), font=font)

    rotated = pattern.rotate(-30, expand=True)
    left = max((rotated.width - image.width) // 2, 0)
    top = max((rotated.height - image.height) // 2, 0)
    overlay = rotated.crop((left, top, left + image.width, top + image.height))

    combined = Image.alpha_composite(image, overlay).convert("RGB")
    out = io.BytesIO()
    combined.save(out, format="JPEG", quality=88)
    return out.getvalue()
