from datetime import datetime
from decimal import Decimal
from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, Boolean, Integer, Numeric, Index, text
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


class LoyaltyRedemption(Base):
    __tablename__ = "loyalty_redemptions"
    __table_args__ = (
        UniqueConstraint("institute_id", "idempotency_key", name="uq_loyalty_redemption_replay"),
        Index("uq_loyalty_redemption_active_line", "ticket_line_id", unique=True,
              sqlite_where=text("reversed_at IS NULL"), postgresql_where=text("reversed_at IS NULL")),
        CheckConstraint("quantity > 0 AND points_cost > 0", name="ck_loyalty_redemption_points"),
        CheckConstraint("currency IN ('CHF', 'EUR')", name="ck_loyalty_redemption_currency"),
        CheckConstraint("original_unit_price > reward_unit_price AND reward_unit_price >= 0 AND "
                        "original_total > reward_total AND reward_total >= 0", name="ck_loyalty_redemption_prices"),
        CheckConstraint("(reversed_at IS NULL AND reversal_entry_id IS NULL AND reversed_by IS NULL AND reversal_reason IS NULL) OR "
                        "(reversed_at IS NOT NULL AND reversal_entry_id IS NOT NULL AND reversed_by IS NOT NULL AND "
                        "reversal_reason IS NOT NULL AND reversed_at >= occurred_at)", name="ck_loyalty_redemption_reversal"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    reward_id: Mapped[str] = mapped_column(ForeignKey("loyalty_rewards.id"))
    ticket_line_id: Mapped[str] = mapped_column(ForeignKey("ticket_lines.id"))
    entry_id: Mapped[str] = mapped_column(ForeignKey("loyalty_entries.id"), unique=True)
    quantity: Mapped[int] = mapped_column(Integer)
    points_cost: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))
    original_unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    original_total: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    reward_unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    reward_total: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    idempotency_key: Mapped[str] = mapped_column(String(120))
    actor_id: Mapped[str] = mapped_column(String(160))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reversal_entry_id: Mapped[str | None] = mapped_column(ForeignKey("loyalty_entries.id"), nullable=True, unique=True)
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reversed_by: Mapped[str | None] = mapped_column(String(160), nullable=True)
    reversal_reason: Mapped[str | None] = mapped_column(String(240), nullable=True)
