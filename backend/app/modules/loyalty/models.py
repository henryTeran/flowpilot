from datetime import datetime
from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base


class LoyaltyEntry(Base):
    __tablename__ = "loyalty_entries"
    __table_args__ = (
        UniqueConstraint("institute_id", "idempotency_key", name="uq_loyalty_entry_replay"),
        CheckConstraint("points <> 0", name="ck_loyalty_entry_points"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    points: Mapped[int] = mapped_column(BigInteger)
    reason: Mapped[str] = mapped_column(String(240))
    idempotency_key: Mapped[str] = mapped_column(String(120))
    actor_id: Mapped[str] = mapped_column(String(160))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class LoyaltyTier(Base):
    __tablename__ = "loyalty_tiers"
    __table_args__ = (
        UniqueConstraint("institute_id", "idempotency_key", name="uq_loyalty_tier_replay"),
        UniqueConstraint("institute_id", "minimum_points", name="uq_loyalty_tier_threshold"),
        CheckConstraint("minimum_points >= 0", name="ck_loyalty_tier_threshold"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    minimum_points: Mapped[int] = mapped_column(BigInteger)
    benefit_description: Mapped[str] = mapped_column(String(240))
    idempotency_key: Mapped[str] = mapped_column(String(120))
    actor_id: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
