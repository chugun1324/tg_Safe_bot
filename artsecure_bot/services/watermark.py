from __future__ import annotations

import io
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont


def add_text_watermark(image_bytes: bytes, order_id: int, artist_nick: str) -> bytes:
    image = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font = ImageFont.load_default()
    watermark = f"ArtSecure | order #{order_id} | {artist_nick} | {datetime.now().strftime('%Y-%m-%d')}"

    text_bbox = draw.textbbox((0, 0), watermark, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]

    x = max((image.width - text_width) // 2, 12)
    y = max(image.height - text_height - 24, 12)

    draw.rectangle(
        [(x - 8, y - 6), (x + text_width + 8, y + text_height + 6)],
        fill=(0, 0, 0, 130),
    )
    draw.text((x, y), watermark, fill=(255, 255, 255, 210), font=font)

    combined = Image.alpha_composite(image, overlay).convert("RGB")
    out = io.BytesIO()
    combined.save(out, format="JPEG", quality=88)
    return out.getvalue()
