from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    bot_token: str
    database_url: str
    admin_ids: set[int]
    support_chat_url: str
    news_channel: str
    rules_article_url: str
    rate_limit_seconds: float
    payments_mode: str
    escrow_wallet_address: str
    cold_wallet_address: str
    fiat_base_currency: str
    payment_rate_source: str
    payment_invoice_ttl_minutes: int
    escrow_review_minutes: int
    escrow_review_poll_seconds: int
    payment_tolerance_bps: int
    payment_provider_name: str
    payment_api_key: str
    payment_api_secret: str
    ton_api_url: str
    ton_api_key: str
    ton_api_insecure_ssl: bool
    ton_usdt_jetton_master: str
    ton_network: str
    escrow_mnemonic: str
    escrow_wallet_version: str
    escrow_jetton_send_ton_amount: float
    manual_usdt_rate_rub: float
    manual_usdt_rate_usd: float
    mock_wallet_balance_usdt: float
    miniapp_url: str
    webapp_host: str
    webapp_port: int



def _parse_admin_ids(raw_value: str) -> set[int]:
    items = [item.strip() for item in raw_value.split(",") if item.strip()]
    return {int(item) for item in items}


def _bool_env(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _require_http_url(value: str, *, env_name: str) -> str:
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RuntimeError(f"{env_name} must be a valid http(s) URL")
    return value.strip()


def load_settings() -> Settings:
    load_dotenv()

    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        raise RuntimeError("BOT_TOKEN is required")

    database_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./artsecure.db").strip()
    support_chat_url = _require_http_url(
        os.getenv("SUPPORT_CHAT_URL", "https://t.me/your_support"),
        env_name="SUPPORT_CHAT_URL",
    )
    news_channel = os.getenv("NEWS_CHANNEL", "@ArtSecureNews").strip()
    rules_article_url = _require_http_url(
        os.getenv("RULES_ARTICLE_URL", "https://example.com/rules_test.html"),
        env_name="RULES_ARTICLE_URL",
    )
    rate_limit_seconds = float(os.getenv("RATE_LIMIT_SECONDS", "1.0"))
    admin_ids = _parse_admin_ids(os.getenv("ADMIN_IDS", ""))
    payments_mode = os.getenv("PAYMENTS_MODE", "mock").strip().lower()
    escrow_wallet_address = os.getenv("ESCROW_WALLET_ADDRESS", "").strip()
    cold_wallet_address = os.getenv("COLD_WALLET_ADDRESS", "").strip()
    fiat_base_currency = os.getenv("FIAT_BASE_CURRENCY", "RUB").strip().upper()
    payment_rate_source = os.getenv("PAYMENT_RATE_SOURCE", "manual").strip().lower()
    payment_invoice_ttl_minutes = int(os.getenv("PAYMENT_INVOICE_TTL_MINUTES", "15"))
    escrow_review_minutes = int(os.getenv("ESCROW_REVIEW_MINUTES", "15"))
    escrow_review_poll_seconds = int(os.getenv("ESCROW_REVIEW_POLL_SECONDS", "10"))
    payment_tolerance_bps = int(os.getenv("PAYMENT_TOLERANCE_BPS", "50"))
    payment_provider_name = os.getenv("PAYMENT_PROVIDER_NAME", "wallet").strip()
    payment_api_key = os.getenv("PAYMENT_API_KEY", "").strip()
    payment_api_secret = os.getenv("PAYMENT_API_SECRET", "").strip()
    ton_api_url = os.getenv("TON_API_URL", "").strip()
    ton_api_key = os.getenv("TON_API_KEY", "").strip()
    ton_api_insecure_ssl = _bool_env("TON_API_INSECURE_SSL", "0")
    allow_insecure_ssl = _bool_env("ALLOW_INSECURE_SSL", "0")
    ton_usdt_jetton_master = os.getenv("TON_USDT_JETTON_MASTER", "").strip()
    ton_network = os.getenv("TON_NETWORK", "mainnet").strip().lower()
    escrow_mnemonic = os.getenv("ESCROW_MNEMONIC", "").strip()
    escrow_wallet_version = os.getenv("ESCROW_WALLET_VERSION", "v4r2").strip().lower()
    escrow_jetton_send_ton_amount = float(os.getenv("ESCROW_JETTON_SEND_TON_AMOUNT", "0.05"))
    manual_usdt_rate_rub = float(os.getenv("MANUAL_USDT_RATE_RUB", "100.0"))
    manual_usdt_rate_usd = float(os.getenv("MANUAL_USDT_RATE_USD", "1.0"))
    mock_wallet_balance_usdt = float(os.getenv("MOCK_WALLET_BALANCE_USDT", "10000.0"))
    miniapp_url = os.getenv("MINIAPP_URL", "").strip().rstrip("/")
    webapp_host = os.getenv("WEBAPP_HOST", "0.0.0.0").strip()
    webapp_port = int(os.getenv("WEBAPP_PORT", "8000"))

    if payments_mode == "ton":
        missing: list[str] = []
        if not escrow_wallet_address:
            missing.append("ESCROW_WALLET_ADDRESS")
        if not cold_wallet_address:
            missing.append("COLD_WALLET_ADDRESS")
        if not ton_api_key:
            missing.append("TON_API_KEY")
        if not ton_usdt_jetton_master:
            missing.append("TON_USDT_JETTON_MASTER")
        if not escrow_mnemonic:
            missing.append("ESCROW_MNEMONIC")
        if missing:
            raise RuntimeError(f"PAYMENTS_MODE=ton requires: {', '.join(missing)}")
        if database_url.startswith("sqlite") and not _bool_env("ALLOW_SQLITE_FOR_TON", "0"):
            raise RuntimeError(
                "DATABASE_URL=sqlite is blocked for PAYMENTS_MODE=ton. "
                "Use PostgreSQL, or set ALLOW_SQLITE_FOR_TON=1 only for local tests."
            )
        if ton_api_insecure_ssl and not allow_insecure_ssl:
            raise RuntimeError("TON_API_INSECURE_SSL=1 is blocked by default. Set ALLOW_INSECURE_SSL=1 only for local debug.")

    return Settings(
        bot_token=bot_token,
        database_url=database_url,
        admin_ids=admin_ids,
        support_chat_url=support_chat_url,
        news_channel=news_channel,
        rules_article_url=rules_article_url,
        rate_limit_seconds=rate_limit_seconds,
        payments_mode=payments_mode,
        escrow_wallet_address=escrow_wallet_address,
        cold_wallet_address=cold_wallet_address,
        fiat_base_currency=fiat_base_currency,
        payment_rate_source=payment_rate_source,
        payment_invoice_ttl_minutes=payment_invoice_ttl_minutes,
        escrow_review_minutes=max(escrow_review_minutes, 1),
        escrow_review_poll_seconds=max(escrow_review_poll_seconds, 5),
        payment_tolerance_bps=payment_tolerance_bps,
        payment_provider_name=payment_provider_name,
        payment_api_key=payment_api_key,
        payment_api_secret=payment_api_secret,
        ton_api_url=ton_api_url,
        ton_api_key=ton_api_key,
        ton_api_insecure_ssl=ton_api_insecure_ssl,
        ton_usdt_jetton_master=ton_usdt_jetton_master,
        ton_network=ton_network,
        escrow_mnemonic=escrow_mnemonic,
        escrow_wallet_version=escrow_wallet_version,
        escrow_jetton_send_ton_amount=escrow_jetton_send_ton_amount,
        manual_usdt_rate_rub=manual_usdt_rate_rub,
        manual_usdt_rate_usd=manual_usdt_rate_usd,
        mock_wallet_balance_usdt=mock_wallet_balance_usdt,
        miniapp_url=miniapp_url,
        webapp_host=webapp_host,
        webapp_port=webapp_port,
    )
