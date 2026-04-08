from __future__ import annotations

import io
import os
import zipfile

from aiogram import Bot

from artsecure_bot.models import ArtAsset


async def build_originals_zip(bot: Bot, order_id: int, assets: list[ArtAsset]) -> bytes | None:
    if not assets:
        return None

    out = io.BytesIO()
    added = 0
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_STORED) as zipf:
        for asset in assets:
            file_id = asset.original_file_id or asset.watermarked_file_id
            if not file_id:
                continue
            try:
                file = await bot.get_file(file_id)
                raw = io.BytesIO()
                await bot.download_file(file.file_path, destination=raw)
            except Exception:
                if asset.original_file_id and asset.watermarked_file_id and file_id == asset.original_file_id:
                    try:
                        file = await bot.get_file(asset.watermarked_file_id)
                        raw = io.BytesIO()
                        await bot.download_file(file.file_path, destination=raw)
                    except Exception:
                        continue
                else:
                    continue

            ext = os.path.splitext(file.file_path or "")[1] or ".bin"
            filename = f"order_{order_id}_asset_{asset.id}{ext}"
            zipf.writestr(filename, raw.getvalue())
            added += 1

    if added == 0:
        return None
    return out.getvalue()
