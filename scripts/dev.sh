#!/usr/bin/env bash
# Dev orchestrator: builds the miniapp, starts an https tunnel pointed at the
# bot's aiohttp server (which serves the built miniapp + the API from one
# port), writes the tunnel URL into .env as MINIAPP_URL, then starts the bot.
# Usage: scripts/dev.sh {start|stop|status}
# Tunnel provider: TUNNEL=cloudflared (default), TUNNEL=ngrok, or TUNNEL=localhostrun
#   TUNNEL=ngrok scripts/dev.sh start
#   TUNNEL=localhostrun scripts/dev.sh start   # no browser-warning page, needs outbound SSH
#
# The miniapp is served as a static production build, not via `vite dev` —
# Vite's HMR websocket client hangs indefinitely inside Telegram Desktop's
# embedded WebView (confirmed: works fine in a plain browser, hangs in real
# Telegram). Run `cd miniapp && npm run dev` separately for fast UI iteration
# in a normal browser tab; re-run `make dev` to rebuild+redeploy for an
# actual in-Telegram test.
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

LOG_DIR="$ROOT_DIR/.dev-logs"
PID_DIR="$ROOT_DIR/.dev-pids"
ENV_FILE="$ROOT_DIR/.env"
TUNNEL_URL_TIMEOUT=30
TUNNEL_PROVIDER="${TUNNEL:-cloudflared}"
WEBAPP_PORT="${WEBAPP_PORT:-8000}"

BOT_PID_FILE="$PID_DIR/bot.pid"
TUNNEL_PID_FILE="$PID_DIR/tunnel.pid"

mkdir -p "$LOG_DIR" "$PID_DIR"

kill_port() {
  local port="$1"
  local pids
  pids=$(lsof -ti "tcp:$port" 2>/dev/null || true)
  if [ -n "$pids" ]; then
    echo "$pids" | xargs kill -9 2>/dev/null || true
  fi
}

stop_one() {
  local file="$1"
  if [ -f "$file" ]; then
    local pid
    pid=$(cat "$file")
    # Child processes (e.g. a backgrounded `npm run dev`'s vite child) can
    # survive their parent's death and keep holding a port — kill children
    # first, then the PID itself.
    pkill -P "$pid" 2>/dev/null || true
    kill "$pid" 2>/dev/null || true
    # aiogram/asyncio's shutdown can hang on SIGTERM (seen repeatedly leaving
    # orphaned bot processes across restarts) — give it a moment, then force.
    for _ in $(seq 1 10); do
      kill -0 "$pid" 2>/dev/null || break
      sleep 0.3
    done
    kill -9 "$pid" 2>/dev/null || true
    rm -f "$file"
  fi
}

stop_all() {
  echo "Stopping bot / tunnel..."
  stop_one "$BOT_PID_FILE"
  stop_one "$TUNNEL_PID_FILE"
  # Safety net: catch any bot process not tracked by the PID file above —
  # e.g. one started manually outside this script, or left over from a
  # restart where the PID file got overwritten before the old process died.
  pkill -9 -f "artsecure_bot\.main" 2>/dev/null || true
  # Safety net: make sure the webapp port is actually free before the next
  # start, regardless of what survived the kills above.
  kill_port "$WEBAPP_PORT"
}

status_one() {
  local name="$1" file="$2"
  if [ -f "$file" ] && kill -0 "$(cat "$file")" 2>/dev/null; then
    echo "  $name: running (pid $(cat "$file"))"
  else
    echo "  $name: stopped"
  fi
}

status() {
  status_one "bot" "$BOT_PID_FILE"
  status_one "tunnel" "$TUNNEL_PID_FILE"
}

update_miniapp_url() {
  local url="$1"
  if grep -q '^MINIAPP_URL=' "$ENV_FILE" 2>/dev/null; then
    sed -i.bak "s#^MINIAPP_URL=.*#MINIAPP_URL=$url#" "$ENV_FILE" && rm -f "$ENV_FILE.bak"
  else
    printf '\nMINIAPP_URL=%s\n' "$url" >> "$ENV_FILE"
  fi
  echo "==> .env MINIAPP_URL set to $url"
}

start_tunnel_cloudflared() {
  if ! command -v cloudflared >/dev/null 2>&1; then
    echo "cloudflared is not installed. Install it with: brew install cloudflared" >&2
    echo "(or run with TUNNEL=ngrok scripts/dev.sh start to use ngrok instead)" >&2
    return 1
  fi

  echo "==> Starting cloudflared tunnel -> http://localhost:$WEBAPP_PORT" >&2
  # --protocol http2: some networks block outbound QUIC/UDP (port 7844), which
  # makes cloudflared print a URL that never actually connects. HTTP/2 falls
  # back to plain TCP/443, which works on most networks (but not all — some
  # networks/VPNs block Cloudflare Tunnel's edge entirely; use TUNNEL=ngrok then).
  cloudflared tunnel --protocol http2 --url http://localhost:$WEBAPP_PORT > "$LOG_DIR/tunnel.log" 2>&1 &
  echo $! > "$TUNNEL_PID_FILE"

  echo "==> Waiting for tunnel URL (up to ${TUNNEL_URL_TIMEOUT}s)..." >&2
  local url=""
  for _ in $(seq 1 "$TUNNEL_URL_TIMEOUT"); do
    url=$(grep -oE 'https://[a-zA-Z0-9.-]+\.trycloudflare\.com' "$LOG_DIR/tunnel.log" 2>/dev/null | head -n1 || true)
    [ -n "$url" ] && break
    sleep 1
  done

  if [ -z "$url" ]; then
    echo "Could not detect the tunnel URL after ${TUNNEL_URL_TIMEOUT}s — check $LOG_DIR/tunnel.log" >&2
    return 1
  fi

  echo "==> Tunnel URL: $url — waiting for it to actually connect..." >&2
  local connected=""
  for _ in $(seq 1 15); do
    if grep -q "Registered tunnel connection" "$LOG_DIR/tunnel.log" 2>/dev/null; then
      connected=1
      break
    fi
    sleep 1
  done
  if [ -z "$connected" ]; then
    echo "WARNING: the URL was printed but no connection registered yet — it likely won't work." >&2
    echo "  Check $LOG_DIR/tunnel.log. Repeated 'TLS handshake with edge error' / 'Failed to" >&2
    echo "  dial a quic connection' means this network/VPN blocks Cloudflare Tunnel's edge" >&2
    echo "  entirely. Try: TUNNEL=ngrok scripts/dev.sh start  (needs an ngrok authtoken, see" >&2
    echo "  https://dashboard.ngrok.com/get-started/your-authtoken)" >&2
  fi

  echo "$url"
}

start_tunnel_ngrok() {
  if ! command -v ngrok >/dev/null 2>&1; then
    echo "ngrok is not installed. Install it with: brew install ngrok" >&2
    return 1
  fi

  echo "==> Starting ngrok tunnel -> http://localhost:$WEBAPP_PORT" >&2
  ngrok http $WEBAPP_PORT --log=stdout > "$LOG_DIR/tunnel.log" 2>&1 &
  echo $! > "$TUNNEL_PID_FILE"

  echo "==> Waiting for ngrok tunnel URL (up to ${TUNNEL_URL_TIMEOUT}s)..." >&2
  local url=""
  for _ in $(seq 1 "$TUNNEL_URL_TIMEOUT"); do
    if grep -qi "ERR_NGROK_4018\|authentication failed" "$LOG_DIR/tunnel.log" 2>/dev/null; then
      echo "ngrok is not authenticated. Run once:" >&2
      echo "  ngrok config add-authtoken <token from https://dashboard.ngrok.com/get-started/your-authtoken>" >&2
      return 1
    fi
    url=$(curl -s http://127.0.0.1:4040/api/tunnels 2>/dev/null | grep -oE '"public_url":"https://[^"]*"' | head -n1 | sed -E 's/.*"(https:[^"]*)"/\1/' || true)
    [ -n "$url" ] && break
    sleep 1
  done

  if [ -z "$url" ]; then
    echo "Could not detect the ngrok tunnel URL after ${TUNNEL_URL_TIMEOUT}s — check $LOG_DIR/tunnel.log" >&2
    return 1
  fi

  echo "$url"
}

start_tunnel_localhostrun() {
  echo "==> Starting localhost.run SSH tunnel -> http://localhost:$WEBAPP_PORT" >&2
  # No signup, no browser-warning interstitial (unlike ngrok's free tier) —
  # useful when the network blocks cloudflared's edge but allows outbound SSH.
  # Connecting with a dedicated key (instead of the anonymous "nokey@" user)
  # ties the subdomain to this key's fingerprint, so it stays stable across
  # restarts instead of rotating (and occasionally dying mid-session) like
  # anonymous tunnels do.
  local key="$HOME/.ssh/localhost_run_ed25519"
  local key_args=()
  local ssh_host="localhost.run"
  if [ -f "$key" ]; then
    # Registered key: no special username — the server identifies the
    # tunnel by the key's fingerprint instead of the anonymous "nokey@" pool.
    key_args=(-i "$key")
  else
    ssh_host="nokey@localhost.run"
  fi
  ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
      -o ServerAliveInterval=30 -o ExitOnForwardFailure=yes \
      "${key_args[@]}" \
      -R 80:localhost:$WEBAPP_PORT "$ssh_host" \
      > "$LOG_DIR/tunnel.log" 2>&1 &
  echo $! > "$TUNNEL_PID_FILE"

  echo "==> Waiting for localhost.run tunnel URL (up to ${TUNNEL_URL_TIMEOUT}s)..." >&2
  local url=""
  for _ in $(seq 1 "$TUNNEL_URL_TIMEOUT"); do
    url=$(grep -oE 'https://[a-zA-Z0-9.-]+\.lhr\.life' "$LOG_DIR/tunnel.log" 2>/dev/null | head -n1 || true)
    [ -n "$url" ] && break
    sleep 1
  done

  if [ -z "$url" ]; then
    echo "Could not detect the localhost.run tunnel URL after ${TUNNEL_URL_TIMEOUT}s — check $LOG_DIR/tunnel.log" >&2
    return 1
  fi

  echo "$url"
}

start_all() {
  if [ ! -f "$ENV_FILE" ]; then
    echo "No .env found in project root — copy .env.example to .env first."
    exit 1
  fi

  # Fresh start: kill anything left over from a previous run.
  stop_all

  echo "==> Tunnel provider: $TUNNEL_PROVIDER"
  url=""
  case "$TUNNEL_PROVIDER" in
    cloudflared) url=$(start_tunnel_cloudflared) ;;
    ngrok) url=$(start_tunnel_ngrok) ;;
    localhostrun) url=$(start_tunnel_localhostrun) ;;
    *)
      echo "Unknown TUNNEL provider: $TUNNEL_PROVIDER (use cloudflared, ngrok, or localhostrun)"
      ;;
  esac

  if [ -z "$url" ]; then
    stop_all
    exit 1
  fi

  update_miniapp_url "$url"

  echo "==> Building miniapp (production bundle — can take a couple minutes)"
  if ! (cd miniapp && npm run build) > "$LOG_DIR/miniapp.log" 2>&1; then
    echo "Miniapp build failed — check $LOG_DIR/miniapp.log"
    stop_all
    exit 1
  fi

  echo "==> Starting bot (serves the API + the built miniapp on :$WEBAPP_PORT)"
  PYTHONUNBUFFERED=1 python3 -m artsecure_bot.main > "$LOG_DIR/bot.log" 2>&1 &
  echo $! > "$BOT_PID_FILE"

  echo ""
  echo "Status:"
  status
  echo ""
  echo "Mini app URL: $url"
  echo "Logs: $LOG_DIR/{bot,miniapp,tunnel}.log  (tail with: make logs)"
  echo "Stop everything with: make stop"
  echo ""
  echo "Note: this serves the production build, not \`vite dev\` — Vite's HMR"
  echo "websocket hangs inside Telegram Desktop's WebView. For fast UI"
  echo "iteration in a plain browser, run 'cd miniapp && npm run dev' in a"
  echo "separate terminal; re-run 'make dev' to rebuild+redeploy for an"
  echo "actual in-Telegram test."
}

case "${1:-start}" in
  start) start_all ;;
  stop) stop_all ;;
  status) status ;;
  *)
    echo "Usage: $0 {start|stop|status}"
    exit 1
    ;;
esac
