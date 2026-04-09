from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import secrets

from sqlalchemy.ext.asyncio import AsyncSession

from artsecure_bot.models import EscrowEvent, EscrowInvoice, Order, OrderStatus, PaymentStatus, User
from artsecure_bot.payments.rates import ManualRateProvider, RateQuote


@dataclass(frozen=True)
class EscrowInvoiceView:
    invoice_id: int
    order_id: int
    payment_address: str
    payment_memo: str
    expected_amount_usdt: str
    fiat_currency: str
    amount_fiat_minor: int
    status: PaymentStatus
    expires_at: datetime


class PaymentEscrowService:
    def __init__(
        self,
        *,
        wallet_address: str,
        invoice_ttl_minutes: int,
        tolerance_bps: int,
        rate_provider: ManualRateProvider,
        provider_name: str,
    ) -> None:
        self._wallet_address = wallet_address
        self._invoice_ttl_minutes = max(invoice_ttl_minutes, 1)
        self._tolerance_bps = max(tolerance_bps, 0)
        self._rate_provider = rate_provider
        self._provider_name = provider_name

    async def create_invoice(
        self,
        session: AsyncSession,
        *,
        order: Order,
        customer: User,
        fiat_currency: str,
        fiat_amount_minor: int,
        payer_wallet_address: str | None,
    ) -> EscrowInvoice:
        if order.customer_id != customer.id:
            raise ValueError("only customer can create invoice")
        if order.status in {OrderStatus.CANCELLED, OrderStatus.COMPLETED}:
            raise ValueError("order already closed")

        quote = self._rate_provider.quote(fiat_currency, fiat_amount_minor)
        now = datetime.now(timezone.utc)
        memo = f"ord{order.id}-{secrets.token_hex(4)}"

        invoice = EscrowInvoice(
            order_id=order.id,
            customer_id=customer.id,
            fiat_currency=quote.fiat_currency,
            amount_fiat_minor=fiat_amount_minor,
            expected_amount_usdt=str(quote.usdt_amount),
            payer_wallet_address=payer_wallet_address,
            payment_address=self._wallet_address,
            payment_memo=memo,
            status=PaymentStatus.AWAITING_PAYMENT,
            tolerance_bps=self._tolerance_bps,
            provider_name=self._provider_name,
            expires_at=now + timedelta(minutes=self._invoice_ttl_minutes),
        )
        session.add(invoice)
        await session.flush()
        await self._log_event(
            session,
            invoice=invoice,
            event_type="invoice_created",
            payload={
                "rate": str(quote.rate_value),
                "source": quote.source,
                "expires_at": invoice.expires_at.isoformat(),
            },
        )
        return invoice

    async def mark_paid_mock(
        self,
        session: AsyncSession,
        *,
        invoice: EscrowInvoice,
        order: Order,
        tx_hash: str,
    ) -> EscrowInvoice:
        if invoice.status not in {
            PaymentStatus.CREATED,
            PaymentStatus.AWAITING_PAYMENT,
            PaymentStatus.PAID_PENDING_CONFIRM,
            PaymentStatus.UNDERPAID,
            PaymentStatus.OVERPAID,
        }:
            raise ValueError("invoice status does not allow payment confirmation")

        invoice.status = PaymentStatus.CONFIRMED
        invoice.tx_hash = tx_hash
        invoice.confirmed_amount_usdt = invoice.expected_amount_usdt
        order.status = OrderStatus.PAID_ESCROW
        order.customer_done = False
        order.artist_done = False
        order.escrow_amount_rub = order.price_rub

        await self._log_event(
            session,
            invoice=invoice,
            event_type="payment_confirmed_mock",
            payload={"tx_hash": tx_hash},
        )
        await session.flush()
        return invoice

    async def mark_released_mock(
        self,
        session: AsyncSession,
        *,
        invoice: EscrowInvoice,
        payout_amount_usdt: str,
        tx_hash: str,
    ) -> EscrowInvoice:
        invoice.status = PaymentStatus.RELEASED
        await self._log_event(
            session,
            invoice=invoice,
            event_type="funds_released_mock",
            payload={"tx_hash": tx_hash, "payout_amount_usdt": payout_amount_usdt},
        )
        await session.flush()
        return invoice

    async def mark_refunded_mock(
        self,
        session: AsyncSession,
        *,
        invoice: EscrowInvoice,
        tx_hash: str,
    ) -> EscrowInvoice:
        invoice.status = PaymentStatus.REFUNDED
        await self._log_event(
            session,
            invoice=invoice,
            event_type="funds_refunded_mock",
            payload={"tx_hash": tx_hash},
        )
        await session.flush()
        return invoice

    async def mark_expired_if_needed(self, session: AsyncSession, invoice: EscrowInvoice) -> bool:
        if invoice.status != PaymentStatus.AWAITING_PAYMENT:
            return False
        expires_at = self._to_aware_utc(invoice.expires_at)
        if expires_at > datetime.now(timezone.utc):
            return False
        invoice.expires_at = expires_at
        invoice.status = PaymentStatus.EXPIRED
        await self._log_event(session, invoice=invoice, event_type="invoice_expired", payload=None)
        await session.flush()
        return True

    def as_view(self, invoice: EscrowInvoice) -> EscrowInvoiceView:
        return EscrowInvoiceView(
            invoice_id=invoice.id,
            order_id=invoice.order_id,
            payment_address=invoice.payment_address,
            payment_memo=invoice.payment_memo,
            expected_amount_usdt=invoice.expected_amount_usdt,
            fiat_currency=invoice.fiat_currency,
            amount_fiat_minor=invoice.amount_fiat_minor,
            status=invoice.status,
            expires_at=invoice.expires_at,
        )

    async def _log_event(
        self,
        session: AsyncSession,
        *,
        invoice: EscrowInvoice,
        event_type: str,
        payload: dict[str, str] | None,
    ) -> None:
        event = EscrowEvent(
            invoice_id=invoice.id,
            order_id=invoice.order_id,
            event_type=event_type,
            payload=json.dumps(payload, ensure_ascii=True) if payload is not None else None,
        )
        session.add(event)
        await session.flush()

    @staticmethod
    def _to_aware_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
