.PHONY: dev stop status logs install

# Starts miniapp (vite) + an https tunnel + the bot, and wires the tunnel's
# https URL into .env as MINIAPP_URL automatically.
# Tunnel defaults to cloudflared; pass TUNNEL=ngrok or TUNNEL=localhostrun
# to use one of those instead (needed if this network blocks Cloudflare
# Tunnel's edge, e.g. some VPNs):
#   make dev TUNNEL=ngrok
# ngrok's free tier shows a browser-warning interstitial page on first visit
# that can hang inside Telegram's in-app WebView. If that happens, use
# localhostrun instead — no interstitial, just needs outbound SSH allowed:
#   make dev TUNNEL=localhostrun
dev:
	@TUNNEL=$(TUNNEL) bash scripts/dev.sh start

stop:
	@bash scripts/dev.sh stop

status:
	@bash scripts/dev.sh status

logs:
	@tail -n 40 -f .dev-logs/bot.log .dev-logs/miniapp.log .dev-logs/tunnel.log

install:
	pip install -r requirements.txt
	cd miniapp && npm install
