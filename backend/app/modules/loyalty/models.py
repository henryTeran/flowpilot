from datetime import datetime
from decimal import Decimal
from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, Boolean, Integer, Numeric
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


class LoyaltyEarningPolicy(Base):
    __tablename__ = "loyalty_earning_policies"
    __table_args__ = (
        UniqueConstraint("institute_id", "idempotency_key", name="uq_loyalty_policy_replay"),
        UniqueConstraint("institute_id", "revision", name="uq_loyalty_policy_revision"),
        CheckConstraint("currency IN ('CHF', 'EUR')", name="ck_loyalty_policy_currency"),
        CheckConstraint("points_per_unit > 0 AND points_per_unit <= 10000 AND revision > 0", name="ck_loyalty_policy_rate"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    points_per_unit: Mapped[Decimal] = mapped_column(Numeric(9, 4))
    enabled: Mapped[bool] = mapped_column(Boolean)
    reason: Mapped[str] = mapped_column(String(240))
    idempotency_key: Mapped[str] = mapped_column(String(120))
    actor_id: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class LoyaltyEarning(Base):
    __tablename__ = "loyalty_earnings"
    __table_args__ = (
        CheckConstraint("currency IN ('CHF', 'EUR')", name="ck_loyalty_earning_currency"),
        CheckConstraint("basis_amount >= 0 AND points >= 0 AND points_per_unit > 0", name="ck_loyalty_earning_amount"),
        CheckConstraint("(points = 0 AND entry_id IS NULL) OR (points > 0 AND entry_id IS NOT NULL)", name="ck_loyalty_earning_entry"),
    )
    ticket_id: Mapped[str] = mapped_column(ForeignKey("queue_tickets.id"), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    policy_id: Mapped[str] = mapped_column(ForeignKey("loyalty_earning_policies.id"))
    entry_id: Mapped[str | None] = mapped_column(ForeignKey("loyalty_entries.id"), nullable=True, unique=True)
    currency: Mapped[str] = mapped_column(String(3))
    basis_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    points_per_unit: Mapped[Decimal] = mapped_column(Numeric(9, 4))
    points: Mapped[int] = mapped_column(BigInteger)
    actor_id: Mapped[str] = mapped_column(String(160))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class LoyaltyReward(Base):
    __tablename__ = "loyalty_rewards"
    __table_args__ = (
        UniqueConstraint("institute_id", "idempotency_key", name="uq_loyalty_reward_replay"),
        CheckConstraint("points_cost > 0 AND minimum_points >= 0", name="ck_loyalty_reward_points"),
        CheckConstraint("discount_amount > 0", name="ck_loyalty_reward_amount"),
        CheckConstraint("currency IN ('CHF', 'EUR')", name="ck_loyalty_reward_currency"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), index=True)
    service_id: Mapped[str] = mapped_column(ForeignKey("services.id"))
    name: Mapped[str] = mapped_column(String(120))
    points_cost: Mapped[int] = mapped_column(BigInteger)
    minimum_points: Mapped[int] = mapped_column(BigInteger)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(3))
    idempotency_key: Mapped[str] = mapped_column(String(120))
    actor_id: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
