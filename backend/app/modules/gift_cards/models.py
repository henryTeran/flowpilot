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
