from datetime import datetime
from decimal import Decimal
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base


class GiftCardSettings(Base):
    __tablename__ = "gift_card_settings"
    __table_args__ = (CheckConstraint("currency IN ('CHF', 'EUR')", name="ck_gift_card_currency"),)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), primary_key=True)
    currency: Mapped[str] = mapped_column(String(3))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    actor_id: Mapped[str] = mapped_column(String(160))


class GiftCardAllocation(Base):
    __tablename__ = "gift_card_allocations"
    __table_args__ = (
        UniqueConstraint("institute_id", "idempotency_key", name="uq_gift_allocation_replay"),
        CheckConstraint("amount > 0", name="ck_gift_allocation_amount"),
        CheckConstraint("currency IN ('CHF', 'EUR')", name="ck_gift_allocation_currency"),
        CheckConstraint("(reversed_at IS NULL AND reversed_by IS NULL AND reversal_reason IS NULL) OR (reversed_at IS NOT NULL AND reversed_by IS NOT NULL AND reversal_reason IS NOT NULL)", name="ck_gift_allocation_reversal"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), index=True)
    card_id: Mapped[str] = mapped_column(ForeignKey("gift_cards.id"), index=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("queue_tickets.id"), index=True)
    currency: Mapped[str] = mapped_column(String(3))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    actor_id: Mapped[str] = mapped_column(String(160))
    idempotency_key: Mapped[str] = mapped_column(String(120))
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reversed_by: Mapped[str | None] = mapped_column(String(160), nullable=True)
    reversal_reason: Mapped[str | None] = mapped_column(String(240), nullable=True)


class GiftTenderClosure(Base):
    __tablename__ = "gift_tender_closures"
    __table_args__ = (
        CheckConstraint("gift_amount > 0 AND remainder_amount >= 0", name="ck_gift_closure_amount"),
        CheckConstraint("currency IN ('CHF', 'EUR')", name="ck_gift_closure_currency"),
        CheckConstraint("(remainder_amount = 0 AND remainder_method IS NULL) OR (remainder_amount > 0 AND remainder_method IS NOT NULL AND remainder_method IN ('cb', 'especes', 'cheque'))", name="ck_gift_closure_remainder"),
    )
    ticket_id: Mapped[str] = mapped_column(ForeignKey("queue_tickets.id"), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), index=True)
    currency: Mapped[str] = mapped_column(String(3))
    gift_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    remainder_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    remainder_method: Mapped[str | None] = mapped_column(String(16), nullable=True)
    actor_id: Mapped[str] = mapped_column(String(160))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class GiftCard(Base):
    __tablename__ = "gift_cards"
    __table_args__ = (
        UniqueConstraint("institute_id", "idempotency_key", name="uq_gift_card_issue_replay"),
        UniqueConstraint("code", name="uq_gift_card_code"),
        CheckConstraint("initial_amount > 0 AND remaining >= 0 AND remaining <= initial_amount", name="ck_gift_card_balance"),
        CheckConstraint("valid_days > 0 AND expires_at > issued_at", name="ck_gift_card_validity"),
        CheckConstraint("currency IN ('CHF', 'EUR')", name="ck_gift_card_issue_currency"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), index=True)
    code: Mapped[str] = mapped_column(String(64))
    currency: Mapped[str] = mapped_column(String(3))
    initial_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    remaining: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    valid_days: Mapped[int] = mapped_column(Integer)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)
    issuance_reason: Mapped[str] = mapped_column(String(240))
    idempotency_key: Mapped[str] = mapped_column(String(120))
    creation_fingerprint: Mapped[str] = mapped_column(String(64))
    actor_id: Mapped[str] = mapped_column(String(160))
