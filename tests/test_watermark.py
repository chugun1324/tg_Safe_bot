import io

from PIL import Image

from artsecure_bot.services.watermark import add_text_watermark


def test_add_text_watermark_returns_jpeg_bytes() -> None:
    image = Image.new("RGB", (320, 200), color=(255, 20, 20))
    source = io.BytesIO()
    image.save(source, format="PNG")

    result = add_text_watermark(source.getvalue(), order_id=42, artist_nick="artist")

    assert isinstance(result, bytes)
    assert len(result) > 1000
    assert result[:2] == b"\xff\xd8"
