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


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    role: Mapped[UserRole] = mapped_column(SQLEnum(UserRole), index=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    nickname: Mapped[str] = mapped_column(String(64))
    contact: Mapped[str] = mapped_column(String(255))
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
    escrow_amount_rub: Mapped[int] = mapped_column(Integer, default=0)
    commission_pct: Mapped[int] = mapped_column(Integer, default=10)
    status: Mapped[OrderStatus] = mapped_column(SQLEnum(OrderStatus), index=True)
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


class BlacklistEntry(Base):
    __tablename__ = "blacklist_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    reason: Mapped[str] = mapped_column(Text())
    created_by_tg_id: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
