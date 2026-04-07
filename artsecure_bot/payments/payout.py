from __future__ import annotations

import asyncio
import ssl
from decimal import Decimal, ROUND_DOWN
from time import monotonic
from typing import Any, Type

import aiohttp
import certifi
from pytoniq_core import Address
from tonutils.clients.http import TonapiClient
from tonutils.contracts.wallet import JettonTransferBuilder, WalletV3R2, WalletV4R2, WalletV5R1
from tonutils.exceptions import (
    NotConnectedError,
    ProviderResponseError,
    ProviderTimeoutError,
    RetryLimitError,
    TransportError,
)
from tonutils.types import NetworkGlobalID
from tonutils.utils import to_nano

from artsecure_bot.config import Settings


class PayoutConfigError(RuntimeError):
    pass


class PayoutTransferError(RuntimeError):
    pass


WALLET_VERSIONS: dict[str, Type] = {
    "v3r2": WalletV3R2,
    "v4r2": WalletV4R2,
    "v5r1": WalletV5R1,
}


NETWORK_MAP = {
    "mainnet": NetworkGlobalID.MAINNET,
    "testnet": NetworkGlobalID.TESTNET,
    "tetra": NetworkGlobalID.TETRA,
}

RETRYABLE_EXCEPTIONS = (
    NotConnectedError,
    ProviderTimeoutError,
    TransportError,
    RetryLimitError,
    aiohttp.ClientError,
    TimeoutError,
    OSError,
)

PAYOUT_MAX_ATTEMPTS = 5
PAYOUT_CONFIRM_TIMEOUT_SECONDS = 180
PAYOUT_CONFIRM_POLL_SECONDS = 8


def _is_retryable_provider_response_error(exc: Exception) -> bool:
    if not isinstance(exc, ProviderResponseError):
        return False
    text = str(exc).lower()
    retryable_markers = (
        "429 rate limit",
        "error code: 429",
        "too many requests",
        "cannot apply external message to current state",
        "inbound external message rejected by account",
        "external message was not accepted",
        "seqno",
    )
    return any(marker in text for marker in retryable_markers)


def _is_rate_limited_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "429" in text or "rate limit" in text or "too many requests" in text


def _retry_delay_seconds(exc: Exception, attempt: int) -> float:
    if _is_rate_limited_error(exc):
        # Free tier TonAPI can throttle aggressively; use a wider backoff window.
        return float(min(45, max(8, attempt * 10)))
    return float(attempt + 1)


def _normalize_raw_address(address: str) -> str:
    return Address(address).to_str(is_user_friendly=False)


def _to_jetton_units(amount_usdt: str) -> int:
    amount = Decimal(amount_usdt).quantize(Decimal("0.000001"), rounding=ROUND_DOWN)
    units = (amount * Decimal("1000000")).to_integral_value(rounding=ROUND_DOWN)
    value = int(units)
    if value <= 0:
        raise PayoutConfigError("invalid_usdt_amount")
    return value


def _mnemonic_words(value: str) -> list[str]:
    words = [w.strip() for w in value.split() if w.strip()]
    if len(words) not in {12, 15, 18, 21, 24}:
        raise PayoutConfigError("invalid_escrow_mnemonic")
    return words


def _wallet_class(version: str):
    cls = WALLET_VERSIONS.get(version)
    if cls is None:
        raise PayoutConfigError("unsupported_wallet_version")
    return cls


def _network(value: str) -> NetworkGlobalID:
    net = NETWORK_MAP.get(value)
    if net is None:
        raise PayoutConfigError("unsupported_ton_network")
    return net


def _create_tonapi_client(
    settings: Settings,
    *,
    network: NetworkGlobalID,
) -> tuple[TonapiClient, aiohttp.ClientSession]:
    if settings.ton_api_insecure_ssl:
        connector = aiohttp.TCPConnector(ssl=False)
    else:
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=ssl_context)

    external_session = aiohttp.ClientSession(
        headers={
            "accept": "application/json",
            "X-API-Key": settings.ton_api_key,
        },
        timeout=aiohttp.ClientTimeout(total=15),
        connector=connector,
    )
    client = TonapiClient(
        network=network,
        api_key=settings.ton_api_key,
        base_url=settings.ton_api_url or None,
        session=external_session,
    )
    return client, external_session


def _create_http_session(settings: Settings) -> aiohttp.ClientSession:
    if settings.ton_api_insecure_ssl:
        connector = aiohttp.TCPConnector(ssl=False)
    else:
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=ssl_context)
    headers = {"accept": "application/json"}
    if settings.ton_api_key:
        headers["X-API-Key"] = settings.ton_api_key
    return aiohttp.ClientSession(
        headers=headers,
        timeout=aiohttp.ClientTimeout(total=15),
        connector=connector,
    )


def _amount_6(amount_usdt: str) -> str:
    return f"{Decimal(amount_usdt).quantize(Decimal('0.000001'), rounding=ROUND_DOWN):.6f}"


def _to_decimal_6(amount_usdt: str) -> Decimal:
    return Decimal(_amount_6(amount_usdt))


async def _wait_for_outgoing_confirmations(
    settings: Settings,
    *,
    transfers: list[tuple[str, str, str]],
    timeout_seconds: int = PAYOUT_CONFIRM_TIMEOUT_SECONDS,
) -> dict[str, str]:
    pending: dict[str, str] = {memo: _amount_6(amount_usdt) for _, amount_usdt, memo in transfers}
    confirmed: dict[str, str] = {}

    deadline = monotonic() + max(1, timeout_seconds)
    while pending and monotonic() < deadline:
        try:
            current_matches = await _fetch_escrow_history_matches(settings, pending)
        except Exception:
            current_matches = {}
        for memo, tx_hash in current_matches.items():
            confirmed[memo] = tx_hash
            pending.pop(memo, None)
        if pending:
            await asyncio.sleep(PAYOUT_CONFIRM_POLL_SECONDS)

    return confirmed


def _extract_address(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        address = (
            value.get("address")
            or value.get("wallet_address")
            or value.get("user_friendly")
            or value.get("raw")
            or ""
        )
        return str(address)
    return str(value) if value is not None else ""


def _extract_memo(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        text = value.get("text") or value.get("comment") or value.get("value")
        return str(text) if text is not None else None
    return str(value)


def _extract_decimals(item: dict[str, Any]) -> int:
    jetton = item.get("jetton") or {}
    raw = item.get("decimals") or jetton.get("decimals") or item.get("jetton_decimals") or 6
    try:
        return int(raw)
    except Exception:
        return 6


def _parse_token_amount(raw: Any, decimals: int) -> Decimal | None:
    try:
        value = str(raw).strip()
        if not value:
            return Decimal("0")
        if "." in value:
            return Decimal(value).quantize(Decimal("0.000001"))
        scale = Decimal("10") ** Decimal(max(decimals, 0))
        return (Decimal(value) / scale).quantize(Decimal("0.000001"))
    except Exception:
        return None


async def _fetch_escrow_history_matches(
    settings: Settings,
    pending: dict[str, str],
) -> dict[str, str]:
    if not pending:
        return {}

    api_url = (settings.ton_api_url or "https://tonapi.io/v2").rstrip("/")
    escrow_wallet = settings.escrow_wallet_address
    url = f"{api_url}/accounts/{escrow_wallet}/jettons/{settings.ton_usdt_jetton_master}/history?limit=100"

    session = _create_http_session(settings)
    try:
        async with session.get(url) as response:
            if response.status >= 400:
                body = await response.text()
                raise RuntimeError(f"tonapi_history_http_{response.status}:{body[:200]}")
            payload = await response.json()
    finally:
        await session.close()

    matched: dict[str, str] = {}
    events = payload.get("events") or []
    for event in events:
        actions = event.get("actions") or []
        for action in actions:
            if action.get("type") != "JettonTransfer":
                continue
            jt = action.get("JettonTransfer") or {}
            memo = _extract_memo(jt.get("comment"))
            if memo is None or memo not in pending:
                continue
            amount_raw = jt.get("amount") or "0"
            decimals = _extract_decimals(jt)
            amount = _parse_token_amount(amount_raw, decimals) or Decimal("0")
            if f"{amount:.6f}" != pending[memo]:
                continue
            tx_hash = ""
            base_transactions = action.get("base_transactions")
            if isinstance(base_transactions, list) and base_transactions:
                tx_hash = str(base_transactions[0])
            if not tx_hash:
                tx_hash = str(action.get("tx_hash") or event.get("event_id") or "")
            if tx_hash:
                matched[memo] = tx_hash
    return matched


def _extract_decimals_from_payload(payload: dict[str, Any]) -> int:
    jetton = payload.get("jetton") or {}
    raw = payload.get("decimals") or jetton.get("decimals") or payload.get("jetton_decimals") or 6
    try:
        return int(raw)
    except Exception:
        return 6


async def _fetch_owner_usdt_balance(settings: Settings, owner_wallet: str) -> Decimal | None:
    api_url = (settings.ton_api_url or "https://tonapi.io/v2").rstrip("/")
    url = f"{api_url}/accounts/{owner_wallet}/jettons/{settings.ton_usdt_jetton_master}"
    session = _create_http_session(settings)
    try:
        async with session.get(url) as response:
            if response.status >= 400:
                return None
            payload = await response.json()
    except Exception:
        return None
    finally:
        await session.close()

    raw_balance = payload.get("balance") or payload.get("amount") or "0"
    decimals = _extract_decimals_from_payload(payload)
    parsed = _parse_token_amount(raw_balance, decimals)
    return parsed


async def _wait_for_escrow_balance_decrease(
    settings: Settings,
    *,
    baseline_balance: Decimal,
    expected_drop: Decimal,
    timeout_seconds: int = PAYOUT_CONFIRM_TIMEOUT_SECONDS,
) -> bool:
    deadline = monotonic() + max(1, timeout_seconds)
    target_balance = (baseline_balance - expected_drop).quantize(Decimal("0.000001"), rounding=ROUND_DOWN)
    while monotonic() < deadline:
        current = await _fetch_owner_usdt_balance(settings, settings.escrow_wallet_address)
        if current is not None and current <= target_balance:
            return True
        await asyncio.sleep(PAYOUT_CONFIRM_POLL_SECONDS)
    return False


def _required_ton_for_jetton_sends(send_count: int, per_send_ton: float) -> Decimal:
    count = max(1, int(send_count))
    per_send = Decimal(str(per_send_ton))
    # Reserve extra TON for wallet gas/storage to avoid "external message rejected".
    reserve = Decimal("0.05")
    return (per_send * Decimal(count)) + reserve


def _nano_to_ton(balance_nano: int) -> Decimal:
    return (Decimal(balance_nano) / Decimal("1000000000")).quantize(Decimal("0.000001"), rounding=ROUND_DOWN)


async def send_usdt_from_escrow(
    *,
    settings: Settings,
    destination_wallet: str,
    amount_usdt: str,
    memo: str,
) -> str:
    if settings.payments_mode != "ton":
        raise PayoutConfigError("payments_mode_not_ton")
    if not settings.ton_api_key:
        raise PayoutConfigError("missing_ton_api_key")
    if not settings.ton_usdt_jetton_master:
        raise PayoutConfigError("missing_usdt_jetton_master")
    if not settings.escrow_mnemonic:
        raise PayoutConfigError("missing_escrow_mnemonic")
    if not settings.escrow_wallet_address:
        raise PayoutConfigError("missing_escrow_wallet")
    if not destination_wallet:
        raise PayoutConfigError("missing_destination_wallet")

    amount_units = _to_jetton_units(amount_usdt)
    amount_decimal = _to_decimal_6(amount_usdt)
    mnemonic = _mnemonic_words(settings.escrow_mnemonic)
    wallet_cls = _wallet_class(settings.escrow_wallet_version)
    network = _network(settings.ton_network)

    last_exc: Exception | None = None
    for attempt in range(1, PAYOUT_MAX_ATTEMPTS + 1):
        client, external_session = _create_tonapi_client(settings, network=network)
        try:
            escrow_balance_before = await _fetch_owner_usdt_balance(settings, settings.escrow_wallet_address)
            await client.connect()
            wallet, *_ = wallet_cls.from_mnemonic(client, mnemonic, validate=True)
            expected_sender_raw = _normalize_raw_address(settings.escrow_wallet_address)
            derived_sender_raw = wallet.address.to_str(is_user_friendly=False)
            if derived_sender_raw != expected_sender_raw:
                raise PayoutConfigError("escrow_wallet_mismatch")
            await wallet.refresh()
            available_ton = _nano_to_ton(wallet.balance)
            required_ton = _required_ton_for_jetton_sends(1, settings.escrow_jetton_send_ton_amount)
            if available_ton < required_ton:
                raise PayoutTransferError(
                    f"insufficient_ton_balance:available={available_ton:.6f},required={required_ton:.6f}"
                )

            builder = JettonTransferBuilder(
                destination=destination_wallet,
                jetton_amount=amount_units,
                jetton_master_address=settings.ton_usdt_jetton_master,
                forward_payload=memo,
                amount=to_nano(str(settings.escrow_jetton_send_ton_amount)),
            )
            external_message = await wallet.transfer_message(builder)
            normalized_hash = getattr(external_message, "normalized_hash", None)
            external_hash = (
                normalized_hash.hex()
                if isinstance(normalized_hash, (bytes, bytearray))
                else str(normalized_hash or "unknown_hash")
            )
            confirmed = await _wait_for_outgoing_confirmations(
                settings,
                transfers=[(destination_wallet, amount_usdt, memo)],
            )
            matched_hash = confirmed.get(memo)
            if matched_hash is None:
                if escrow_balance_before is not None:
                    decreased = await _wait_for_escrow_balance_decrease(
                        settings,
                        baseline_balance=escrow_balance_before,
                        expected_drop=amount_decimal,
                    )
                    if decreased:
                        return external_hash
                raise PayoutTransferError(f"outgoing_transfer_not_confirmed:{external_hash}")
            return matched_hash
        except PayoutConfigError:
            raise
        except PayoutTransferError:
            raise
        except Exception as exc:
            last_exc = exc
            is_retryable = isinstance(exc, RETRYABLE_EXCEPTIONS) or _is_retryable_provider_response_error(exc)
            if is_retryable and attempt < PAYOUT_MAX_ATTEMPTS:
                await asyncio.sleep(_retry_delay_seconds(exc, attempt))
                continue
            raise PayoutTransferError(str(exc)) from exc
        finally:
            try:
                await client.close()
            except Exception:
                pass
            if external_session is not None and not external_session.closed:
                try:
                    await external_session.close()
                except Exception:
                    pass

    if last_exc is not None:
        raise PayoutTransferError(str(last_exc)) from last_exc
    raise PayoutTransferError("unknown_payout_error")


async def send_usdt_from_escrow_batch(
    *,
    settings: Settings,
    transfers: list[tuple[str, str, str]],
) -> str:
    if settings.payments_mode != "ton":
        raise PayoutConfigError("payments_mode_not_ton")
    if not settings.ton_api_key:
        raise PayoutConfigError("missing_ton_api_key")
    if not settings.ton_usdt_jetton_master:
        raise PayoutConfigError("missing_usdt_jetton_master")
    if not settings.escrow_mnemonic:
        raise PayoutConfigError("missing_escrow_mnemonic")
    if not settings.escrow_wallet_address:
        raise PayoutConfigError("missing_escrow_wallet")
    if not transfers:
        raise PayoutConfigError("missing_destination_wallet")

    mnemonic = _mnemonic_words(settings.escrow_mnemonic)
    wallet_cls = _wallet_class(settings.escrow_wallet_version)
    network = _network(settings.ton_network)

    prepared_builders: list[JettonTransferBuilder] = []
    total_amount_decimal = Decimal("0")
    for destination_wallet, amount_usdt, memo in transfers:
        if not destination_wallet:
            raise PayoutConfigError("missing_destination_wallet")
        amount_units = _to_jetton_units(amount_usdt)
        total_amount_decimal += _to_decimal_6(amount_usdt)
        prepared_builders.append(
            JettonTransferBuilder(
                destination=destination_wallet,
                jetton_amount=amount_units,
                jetton_master_address=settings.ton_usdt_jetton_master,
                forward_payload=memo,
                amount=to_nano(str(settings.escrow_jetton_send_ton_amount)),
            )
        )

    last_exc: Exception | None = None
    for attempt in range(1, PAYOUT_MAX_ATTEMPTS + 1):
        client, external_session = _create_tonapi_client(settings, network=network)
        try:
            escrow_balance_before = await _fetch_owner_usdt_balance(settings, settings.escrow_wallet_address)
            await client.connect()
            wallet, *_ = wallet_cls.from_mnemonic(client, mnemonic, validate=True)
            expected_sender_raw = _normalize_raw_address(settings.escrow_wallet_address)
            derived_sender_raw = wallet.address.to_str(is_user_friendly=False)
            if derived_sender_raw != expected_sender_raw:
                raise PayoutConfigError("escrow_wallet_mismatch")
            await wallet.refresh()
            available_ton = _nano_to_ton(wallet.balance)
            required_ton = _required_ton_for_jetton_sends(len(transfers), settings.escrow_jetton_send_ton_amount)
            if available_ton < required_ton:
                raise PayoutTransferError(
                    f"insufficient_ton_balance:available={available_ton:.6f},required={required_ton:.6f}"
                )

            external_message = await wallet.batch_transfer_message(prepared_builders)
            normalized_hash = getattr(external_message, "normalized_hash", None)
            external_hash = (
                normalized_hash.hex()
                if isinstance(normalized_hash, (bytes, bytearray))
                else str(normalized_hash or "unknown_hash")
            )
            confirmed = await _wait_for_outgoing_confirmations(settings, transfers=transfers)
            if len(confirmed) != len(transfers):
                missing = [memo for _, _, memo in transfers if memo not in confirmed]
                if escrow_balance_before is not None:
                    decreased = await _wait_for_escrow_balance_decrease(
                        settings,
                        baseline_balance=escrow_balance_before,
                        expected_drop=total_amount_decimal,
                    )
                    if decreased:
                        return external_hash
                raise PayoutTransferError(
                    f"outgoing_batch_not_confirmed:{external_hash}:missing={','.join(missing)}"
                )
            first_memo = transfers[0][2]
            first_hash = confirmed.get(first_memo)
            if first_hash is None:
                raise PayoutTransferError(f"outgoing_batch_not_confirmed:{external_hash}:missing_first")
            return first_hash
        except PayoutConfigError:
            raise
        except PayoutTransferError:
            raise
        except Exception as exc:
            last_exc = exc
            is_retryable = isinstance(exc, RETRYABLE_EXCEPTIONS) or _is_retryable_provider_response_error(exc)
            if is_retryable and attempt < PAYOUT_MAX_ATTEMPTS:
                await asyncio.sleep(_retry_delay_seconds(exc, attempt))
                continue
            raise PayoutTransferError(str(exc)) from exc
        finally:
            try:
                await client.close()
            except Exception:
                pass
            if external_session is not None and not external_session.closed:
                try:
                    await external_session.close()
                except Exception:
                    pass

    if last_exc is not None:
        raise PayoutTransferError(str(last_exc)) from last_exc
    raise PayoutTransferError("unknown_payout_error")
