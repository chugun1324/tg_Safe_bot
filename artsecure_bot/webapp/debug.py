from __future__ import annotations

import hashlib
import hmac
from urllib.parse import parse_qsl

from aiohttp import web

DEBUG_HTML = """<!doctype html>
<html>
<head><meta charset="utf-8"><title>Mini App Debug</title></head>
<body style="font-family:monospace;white-space:pre-wrap;word-break:break-all;padding:16px;background:#0f1729;color:#e5e7eb;">
<h3>Mini App initData Debug</h3>
<div id="out">loading...</div>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<script>
const out = document.getElementById('out');
function log(s) { out.textContent += s + "\\n\\n"; }
try {
  const tg = window.Telegram && window.Telegram.WebApp;
  log("Telegram.WebApp present: " + !!tg);
  log("initData length: " + (tg && tg.initData ? tg.initData.length : 0));
  log("initData raw:\\n" + (tg ? tg.initData : "(no tg)"));
  log("initDataUnsafe:\\n" + JSON.stringify(tg ? tg.initDataUnsafe : null, null, 2));
  fetch('/debug-init', {
    headers: { 'X-Telegram-Init-Data': tg && tg.initData ? tg.initData : '' }
  }).then(r => r.json()).then(d => {
    log("Server check:\\n" + JSON.stringify(d, null, 2));
  }).catch(e => log("fetch error: " + e));
} catch (e) {
  log("error: " + e);
}
</script>
</body>
</html>"""


async def debug_page(_request: web.Request) -> web.Response:
    return web.Response(text=DEBUG_HTML, content_type="text/html")


async def debug_init(request: web.Request) -> web.Response:
    bot_token = request.app["bot_token"]
    init_data = request.headers.get("X-Telegram-Init-Data", "")

    if not init_data:
        return web.json_response({"error": "empty initData header"})

    try:
        pairs = parse_qsl(init_data, strict_parsing=True, keep_blank_values=True)
    except ValueError as exc:
        return web.json_response({"error": f"parse_qsl failed: {exc}", "raw_len": len(init_data), "raw": init_data})

    data = dict(pairs)
    received_hash = data.pop("hash", None)
    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(data.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

    return web.json_response(
        {
            "raw_len": len(init_data),
            "raw": init_data,
            "parsed_field_count": len(data),
            "parsed_fields": list(data.keys()),
            "data_check_string": data_check_string,
            "received_hash": received_hash,
            "computed_hash": computed_hash,
            "match": hmac.compare_digest(computed_hash, received_hash or ""),
            "bot_token_fingerprint": hashlib.sha256(bot_token.encode()).hexdigest()[:16],
        }
    )
