from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import aiohttp


@dataclass(frozen=True)
class IncomingTransfer:
    tx_hash: str
    source_wallet: str
    amount_usdt: Decimal
    memo: str | None


class MockWalletGateway:
    def __init__(self, mock_balance_usdt: float) -> None:
        self._mock_balance = Decimal(str(mock_balance_usdt))

    async def has_enough_usdt(self, wallet_address: str, needed_amount_usdt: Decimal) -> bool:
        if not wallet_address:
            return False
        return self._mock_balance >= needed_amount_usdt

    async def wallet_exists(self, wallet_address: str) -> bool | None:
        return bool(wallet_address)

    async def find_matching_transfer(
        self,
        *,
        escrow_wallet: str,
        payer_wallet: str,
        memo: str,
        expected_amount: Decimal,
    ) -> IncomingTransfer | None:
        # In mock flow transfer is confirmed manually via /mock_paid.
        return None


class TonWalletGateway:
    """Best-effort TON API integration for wallet checks.

    Note: endpoints can differ by provider version, therefore parser is defensive.
    """

    def __init__(self, api_url: str, api_key: str, usdt_jetton_master: str) -> None:
        self._api_url = api_url.rstrip("/")
        self._api_key = api_key
        self._usdt_jetton_master = usdt_jetton_master

    def _headers(self) -> dict[str, str]:
        headers = {"accept": "application/json"}
        if self._api_key:
            headers["X-API-Key"] = self._api_key
        return headers

    async def _get_json(self, url: str) -> dict[str, Any] | None:
        headers = self._headers()
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(url, timeout=15) as response:
                    if response.status != 200:
                        return None
                    return await response.json()
        except aiohttp.ClientSSLError:
            try:
                async with aiohttp.ClientSession(headers=headers) as session:
                    async with session.get(url, timeout=15, ssl=False) as response:
                        if response.status != 200:
                            return None
                        return await response.json()
            except Exception:
                return None
        except Exception:
            return None

    async def has_enough_usdt(self, wallet_address: str, needed_amount_usdt: Decimal) -> bool:
        balance = await self._fetch_usdt_balance(wallet_address)
        if balance is None:
            # Some custodial wallets (for example Telegram Wallet internal accounting)
            # can return no readable on-chain balance via public APIs.
            # Do not hard-block invoice creation in this case; actual transfer still
            # fails on wallet side if funds are really insufficient.
            return True
        return balance >= needed_amount_usdt

    async def wallet_exists(self, wallet_address: str) -> bool | None:
        if not wallet_address:
            return False
        payload = await self._get_json(f"{self._api_url}/accounts/{wallet_address}")
        if payload is None:
            return None
        status = str(payload.get("status") or "").lower()
        if status in {"nonexist", "uninitialized", "uninit"}:
            return False
        return True

    async def find_matching_transfer(
        self,
        *,
        escrow_wallet: str,
        payer_wallet: str,
        memo: str,
        expected_amount: Decimal,
    ) -> IncomingTransfer | None:
        transfer = await self._find_matching_transfer_account_history(
            escrow_wallet=escrow_wallet,
            payer_wallet=payer_wallet,
            memo=memo,
            expected_amount=expected_amount,
        )
        if transfer is not None:
            return transfer
        # Legacy fallback for providers that expose this endpoint.
        return await self._find_matching_transfer_legacy(
            escrow_wallet=escrow_wallet,
            payer_wallet=payer_wallet,
            memo=memo,
            expected_amount=expected_amount,
        )

    async def _find_matching_transfer_account_history(
        self,
        *,
        escrow_wallet: str,
        payer_wallet: str,
        memo: str,
        expected_amount: Decimal,
    ) -> IncomingTransfer | None:
        escrow_wallet_lc = escrow_wallet.lower() if escrow_wallet else ""
        escrow_jetton_wallet_lc = await self._fetch_owner_jetton_wallet_address_lc(escrow_wallet)
        payer_wallet_lc = payer_wallet.lower() if payer_wallet else ""
        payer_jetton_wallet_lc = await self._fetch_owner_jetton_wallet_address_lc(payer_wallet)
        url = (
            f"{self._api_url}/accounts/{escrow_wallet}/jettons/{self._usdt_jetton_master}/history?limit=100"
        )
        payload = await self._get_json(url)
        if payload is None:
            return None

        events = payload.get("events") or []
        expected_str = f"{expected_amount:.6f}"
        for event in events:
            actions = event.get("actions") or []
            for action in actions:
                if action.get("type") != "JettonTransfer":
                    continue
                jt = action.get("JettonTransfer") or {}
                sender_owner = self._extract_address(jt.get("sender"))
                recipient_owner = self._extract_address(jt.get("recipient"))
                sender_wallet = self._extract_address(jt.get("senders_wallet"))
                recipient_wallet = self._extract_address(jt.get("recipients_wallet"))
                amount_raw = jt.get("amount") or "0"
                decimals = self._extract_decimals(jt)
                amount = self._parse_token_amount(amount_raw, decimals) or Decimal("0")
                memo_text = self._extract_memo(jt.get("comment"))

                destination_candidates = {
                    recipient_owner.lower() if recipient_owner else "",
                    recipient_wallet.lower() if recipient_wallet else "",
                }
                destination_candidates.discard("")
                if escrow_wallet_lc and escrow_wallet_lc not in destination_candidates:
                    if escrow_jetton_wallet_lc is None or escrow_jetton_wallet_lc not in destination_candidates:
                        continue

                source_candidates = {
                    sender_owner.lower() if sender_owner else "",
                    sender_wallet.lower() if sender_wallet else "",
                }
                source_candidates.discard("")
                # Some users pay from another wallet app/account than previously saved via /set_wallet.
                # For MVP we accept transfer if memo+amount+destination match exactly.
                # If payer wallet matches, it's an additional positive signal only.
                _payer_matches = (
                    not payer_wallet_lc
                    or payer_wallet_lc in source_candidates
                    or (payer_jetton_wallet_lc is not None and payer_jetton_wallet_lc in source_candidates)
                )

                if memo_text is None or memo not in memo_text:
                    continue
                if f"{amount:.6f}" != expected_str:
                    continue

                tx_hash = ""
                base_transactions = action.get("base_transactions")
                if isinstance(base_transactions, list) and base_transactions:
                    tx_hash = str(base_transactions[0])
                if not tx_hash:
                    tx_hash = str(action.get("tx_hash") or event.get("event_id") or "")
                if not tx_hash:
                    continue

                source_wallet = sender_owner or sender_wallet
                return IncomingTransfer(
                    tx_hash=tx_hash,
                    source_wallet=source_wallet,
                    amount_usdt=amount,
                    memo=memo_text,
                )
        return None

    async def _find_matching_transfer_legacy(
        self,
        *,
        escrow_wallet: str,
        payer_wallet: str,
        memo: str,
        expected_amount: Decimal,
    ) -> IncomingTransfer | None:
        escrow_wallet_lc = escrow_wallet.lower() if escrow_wallet else ""
        escrow_jetton_wallet_lc = await self._fetch_owner_jetton_wallet_address_lc(escrow_wallet)
        payer_wallet_lc = payer_wallet.lower() if payer_wallet else ""
        payer_jetton_wallet_lc = await self._fetch_owner_jetton_wallet_address_lc(payer_wallet)
        url = f"{self._api_url}/jetton/transfers?jetton_address={self._usdt_jetton_master}&limit=100&sort=desc"
        payload = await self._get_json(url)
        if payload is None:
            return None

        items = payload.get("jetton_transfers") or payload.get("transfers") or payload.get("items") or []
        expected_str = f"{expected_amount:.6f}"
        for item in items:
            source = self._extract_address(
                item.get("source")
                or item.get("from")
                or item.get("sender")
                or item.get("from_address")
                or ""
            )
            destination = self._extract_address(
                item.get("destination")
                or item.get("to")
                or item.get("recipient")
                or item.get("to_address")
                or ""
            )
            tx_hash = item.get("transaction_hash") or item.get("tx_hash") or item.get("hash") or ""
            raw_memo = (
                item.get("comment")
                or item.get("memo")
                or item.get("forward_payload")
                or item.get("decoded_comment")
            )
            if not tx_hash or not source or not destination:
                continue
            destination_lc = destination.lower()
            if escrow_wallet_lc and destination_lc != escrow_wallet_lc:
                if escrow_jetton_wallet_lc is None or destination_lc != escrow_jetton_wallet_lc:
                    continue
            amount = self._extract_amount(item)
            source_lc = source.lower()
            _payer_matches = (
                not payer_wallet_lc
                or source_lc == payer_wallet_lc
                or (payer_jetton_wallet_lc is not None and source_lc == payer_jetton_wallet_lc)
            )
            memo_text = self._extract_memo(raw_memo)
            # Memo is mandatory for reliable order matching.
            if memo_text is None or memo not in memo_text:
                continue
            if f"{amount:.6f}" != expected_str:
                continue
            return IncomingTransfer(
                tx_hash=tx_hash,
                source_wallet=source,
                amount_usdt=amount,
                memo=memo_text,
            )
        return None

    async def _fetch_owner_jetton_wallet_address_lc(self, owner_wallet: str) -> str | None:
        if not owner_wallet:
            return None

        url = f"{self._api_url}/accounts/{owner_wallet}/jettons/{self._usdt_jetton_master}"
        payload = await self._get_json(url)
        if payload is None:
            return await self._fetch_owner_jetton_wallet_address_lc_legacy(owner_wallet)

        address = self._extract_address(
            payload.get("wallet_address")
            or payload.get("address")
            or payload.get("jetton_wallet_address")
            or ""
        )
        return address.lower() if address else None

    async def _fetch_owner_jetton_wallet_address_lc_legacy(self, owner_wallet: str) -> str | None:
        url = (
            f"{self._api_url}/jetton/wallets"
            f"?owner_address={owner_wallet}&jetton_address={self._usdt_jetton_master}"
        )
        payload = await self._get_json(url)
        if payload is None:
            return None
        wallets = payload.get("jetton_wallets") or payload.get("wallets") or payload.get("items") or []
        if not wallets:
            return None
        address = self._extract_address(
            wallets[0].get("address")
            or wallets[0].get("wallet_address")
            or wallets[0].get("jetton_wallet_address")
            or ""
        )
        return address.lower() if address else None

    async def _fetch_usdt_balance(self, wallet_address: str) -> Decimal | None:
        if not wallet_address:
            return None

        url = (
            f"{self._api_url}/jetton/wallets"
            f"?owner_address={wallet_address}&jetton_address={self._usdt_jetton_master}"
        )
        payload = await self._get_json(url)
        if payload is not None:
            balance = self._parse_jetton_wallets_balance(payload)
            if balance is not None:
                return balance
        return await self._fetch_usdt_balance_fallback(wallet_address)

    async def _fetch_usdt_balance_fallback(self, wallet_address: str) -> Decimal | None:
        # Fallback endpoint used by some TON API versions.
        url = f"{self._api_url}/accounts/{wallet_address}/jettons"
        payload = await self._get_json(url)
        if payload is None:
            return None

        balances = payload.get("balances") or payload.get("jettons") or payload.get("items") or []
        for item in balances:
            jetton = item.get("jetton") or {}
            jetton_address = (
                jetton.get("address")
                or item.get("jetton_address")
                or item.get("address")
                or ""
            )
            if not jetton_address or jetton_address != self._usdt_jetton_master:
                continue
            decimals = self._extract_decimals(item)
            raw = item.get("balance") or item.get("amount") or "0"
            parsed = self._parse_token_amount(raw, decimals)
            if parsed is not None:
                return parsed
        return Decimal("0")

    def _parse_jetton_wallets_balance(self, payload: dict[str, Any]) -> Decimal | None:
        wallets = payload.get("jetton_wallets") or payload.get("wallets") or payload.get("items") or []
        if not wallets:
            return Decimal("0")
        for wallet in wallets:
            decimals = self._extract_decimals(wallet)
            raw = wallet.get("balance") or wallet.get("amount") or "0"
            parsed = self._parse_token_amount(raw, decimals)
            if parsed is not None:
                return parsed
        return None

    @staticmethod
    def _extract_decimals(item: dict[str, Any]) -> int:
        jetton = item.get("jetton") or {}
        raw = (
            item.get("decimals")
            or jetton.get("decimals")
            or item.get("jetton_decimals")
            or 6
        )
        try:
            return int(raw)
        except Exception:
            return 6

    @staticmethod
    def _parse_token_amount(raw: Any, decimals: int) -> Decimal | None:
        try:
            value = str(raw).strip()
            if not value:
                return Decimal("0")
            # If provider already returns human amount like "12.345",
            # do not scale by decimals.
            if "." in value:
                return Decimal(value).quantize(Decimal("0.000001"))
            scale = Decimal("10") ** Decimal(max(decimals, 0))
            return (Decimal(value) / scale).quantize(Decimal("0.000001"))
        except Exception:
            return None

    @staticmethod
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

    @staticmethod
    def _extract_memo(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            text = value.get("text") or value.get("comment") or value.get("value")
            return str(text) if text is not None else None
        return str(value)

    @staticmethod
    def _extract_amount(item: dict[str, Any]) -> Decimal:
        raw = item.get("amount") or item.get("jetton_amount") or item.get("value") or "0"
        decimals_raw = item.get("jetton_decimals") or item.get("decimals") or 6
        try:
            decimals = int(decimals_raw)
        except Exception:
            decimals = 6
        parsed = TonWalletGateway._parse_token_amount(raw, decimals)
        return parsed if parsed is not None else Decimal("0")
