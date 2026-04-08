from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    bot_token: str
    database_url: str
    admin_ids: set[int]
    support_chat_url: str
    news_channel: str
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



def _parse_admin_ids(raw_value: str) -> set[int]:
    items = [item.strip() for item in raw_value.split(",") if item.strip()]
    return {int(item) for item in items}


def load_settings() -> Settings:
    load_dotenv()

    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        raise RuntimeError("BOT_TOKEN is required")

    database_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./artsecure.db").strip()
    support_chat_url = os.getenv("SUPPORT_CHAT_URL", "https://t.me/your_support").strip()
    news_channel = os.getenv("NEWS_CHANNEL", "@ArtSecureNews").strip()
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
    ton_api_insecure_ssl = os.getenv("TON_API_INSECURE_SSL", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    ton_usdt_jetton_master = os.getenv("TON_USDT_JETTON_MASTER", "").strip()
    ton_network = os.getenv("TON_NETWORK", "mainnet").strip().lower()
    escrow_mnemonic = os.getenv("ESCROW_MNEMONIC", "").strip()
    escrow_wallet_version = os.getenv("ESCROW_WALLET_VERSION", "v4r2").strip().lower()
    escrow_jetton_send_ton_amount = float(os.getenv("ESCROW_JETTON_SEND_TON_AMOUNT", "0.05"))
    manual_usdt_rate_rub = float(os.getenv("MANUAL_USDT_RATE_RUB", "100.0"))
    manual_usdt_rate_usd = float(os.getenv("MANUAL_USDT_RATE_USD", "1.0"))
    mock_wallet_balance_usdt = float(os.getenv("MOCK_WALLET_BALANCE_USDT", "10000.0"))

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

    return Settings(
        bot_token=bot_token,
        database_url=database_url,
        admin_ids=admin_ids,
        support_chat_url=support_chat_url,
        news_channel=news_channel,
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
    )
