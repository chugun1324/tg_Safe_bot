from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import BigInteger, Boolean, DateTime, Enum as SQLEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class UserRole(str, Enum):
    CUSTOMER = "customer"
    ARTIST = "artist"
    ADMIN = "admin"


class OrderStatus(str, Enum):
    PENDING_ARTIST = "pending_artist"
    IN_PROGRESS = "in_progress"
    PREVIEW_SENT = "preview_sent"
    PAID_ESCROW = "paid_escrow"
    FINAL_REVIEW = "final_review"
    COMPLETED = "completed"
    DISPUTED = "disputed"
    CANCELLED = "cancelled"


class ArtKind(str, Enum):
    PREVIEW = "preview"
    FINAL = "final"


class ReportStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"


class PaymentStatus(str, Enum):
    CREATED = "created"
    AWAITING_PAYMENT = "awaiting_payment"
    PAID_PENDING_CONFIRM = "paid_pending_confirm"
    CONFIRMED = "confirmed"
    UNDERPAID = "underpaid"
    OVERPAID = "overpaid"
    EXPIRED = "expired"
    RELEASED = "released"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    role: Mapped[UserRole] = mapped_column(SQLEnum(UserRole), index=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    nickname: Mapped[str] = mapped_column(String(64))
    contact: Mapped[str] = mapped_column(String(255))
    wallet_address: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    premium_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    customer_orders: Mapped[list[Order]] = relationship(
        "Order", back_populates="customer", foreign_keys="Order.customer_id"
    )
    artist_orders: Mapped[list[Order]] = relationship(
        "Order", back_populates="artist", foreign_keys="Order.artist_id"
    )


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    artist_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    details: Mapped[str] = mapped_column(Text())
    price_rub: Mapped[int] = mapped_column(Integer)
    price_amount: Mapped[str] = mapped_column(String(32), default="0")
    price_currency: Mapped[str] = mapped_column(String(8), default="RUB")
    escrow_amount_rub: Mapped[int] = mapped_column(Integer, default=0)
    commission_pct: Mapped[int] = mapped_column(Integer, default=10)
    customer_done: Mapped[bool] = mapped_column(Boolean, default=False)
    artist_done: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[OrderStatus] = mapped_column(SQLEnum(OrderStatus), index=True)
    status_before_dispute: Mapped[OrderStatus | None] = mapped_column(SQLEnum(OrderStatus), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    customer: Mapped[User] = relationship(
        "User", back_populates="customer_orders", foreign_keys=[customer_id]
    )
    artist: Mapped[User] = relationship("User", back_populates="artist_orders", foreign_keys=[artist_id])

    assets: Mapped[list[ArtAsset]] = relationship("ArtAsset", back_populates="order")
    reports: Mapped[list[Report]] = relationship("Report", back_populates="order")
    escrow_invoices: Mapped[list[EscrowInvoice]] = relationship("EscrowInvoice", back_populates="order")


class ArtAsset(Base):
    __tablename__ = "art_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[ArtKind] = mapped_column(SQLEnum(ArtKind), index=True)
    original_file_id: Mapped[str] = mapped_column(String(255))
    watermarked_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    order: Mapped[Order] = relationship("Order", back_populates="assets")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    target_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
    reason: Mapped[str] = mapped_column(Text())
    status: Mapped[ReportStatus] = mapped_column(SQLEnum(ReportStatus), default=ReportStatus.OPEN)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    order: Mapped[Order | None] = relationship("Order", back_populates="reports")


class EscrowInvoice(Base):
    __tablename__ = "escrow_invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    fiat_currency: Mapped[str] = mapped_column(String(8), default="RUB")
    amount_fiat_minor: Mapped[int] = mapped_column(Integer)
    expected_amount_usdt: Mapped[str] = mapped_column(String(32))
    payer_wallet_address: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payment_address: Mapped[str] = mapped_column(String(255))
    payment_memo: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    status: Mapped[PaymentStatus] = mapped_column(
        SQLEnum(PaymentStatus),
        default=PaymentStatus.CREATED,
        index=True,
    )
    tolerance_bps: Mapped[int] = mapped_column(Integer, default=50)
    provider_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider_invoice_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tx_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confirmed_amount_usdt: Mapped[str | None] = mapped_column(String(32), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    order: Mapped[Order] = relationship("Order", back_populates="escrow_invoices")
    events: Mapped[list[EscrowEvent]] = relationship("EscrowEvent", back_populates="invoice")


class EscrowEvent(Base):
    __tablename__ = "escrow_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("escrow_invoices.id"), index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    invoice: Mapped[EscrowInvoice] = relationship("EscrowInvoice", back_populates="events")


class BlacklistEntry(Base):
    __tablename__ = "blacklist_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    reason: Mapped[str] = mapped_column(Text())
    created_by_tg_id: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class UserLocale(Base):
    __tablename__ = "user_locales"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    language: Mapped[str] = mapped_column(String(8), default="ru")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
