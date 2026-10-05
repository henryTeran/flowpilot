from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base


class MembershipPlan(Base):
    __tablename__ = "membership_plans"
    __table_args__ = (
        UniqueConstraint("institute_id", "idempotency_key", name="uq_membership_plan_replay"),
        CheckConstraint("valid_days > 0", name="ck_membership_plan_days"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    valid_days: Mapped[int] = mapped_column(Integer)
    idempotency_key: Mapped[str] = mapped_column(String(120))
    creation_fingerprint: Mapped[str] = mapped_column(String(64))
    actor_id: Mapped[str | None] = mapped_column(String(160), nullable=True)


class CustomerMembership(Base):
    __tablename__ = "customer_memberships"
    __table_args__ = (
        UniqueConstraint("institute_id", "idempotency_key", name="uq_membership_issue_replay"),
        CheckConstraint("valid_days > 0 AND active_until > active_from AND active_from >= issued_at", name="ck_membership_term"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), index=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey("membership_plans.id"))
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    valid_days: Mapped[int] = mapped_column(Integer)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    active_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    active_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str] = mapped_column(String(120))
    actor_id: Mapped[str | None] = mapped_column(String(160), nullable=True)


class MembershipRenewal(Base):
    __tablename__ = "membership_renewals"
    __table_args__ = (
        UniqueConstraint("institute_id", "idempotency_key", name="uq_membership_renewal_replay"),
        CheckConstraint("previous_until > previous_from AND active_until > active_from AND "
                        "active_until > previous_until AND active_from >= previous_from AND occurred_at >= previous_from",
                        name="ck_membership_renewal_term"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), index=True)
    membership_id: Mapped[str] = mapped_column(ForeignKey("customer_memberships.id"), index=True)
    previous_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    previous_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    active_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    active_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str] = mapped_column(String(120))
    actor_id: Mapped[str | None] = mapped_column(String(160), nullable=True)


class MembershipBenefit(Base):
    __tablename__ = "membership_benefits"
    __table_args__ = (
        UniqueConstraint("institute_id", "idempotency_key", name="uq_membership_benefit_replay"),
        Index("uq_membership_benefit_active_line", "ticket_line_id", unique=True,
              sqlite_where=text("reversed_at IS NULL"), postgresql_where=text("reversed_at IS NULL")),
        CheckConstraint("quantity > 0 AND original_unit_price >= 0 AND original_total >= 0 AND "
                        "member_unit_price >= 0 AND member_total >= 0 AND member_unit_price < original_unit_price "
                        "AND member_total < original_total", name="ck_membership_benefit_prices"),
        CheckConstraint("(reversed_at IS NULL AND reversed_by IS NULL AND reversal_reason IS NULL) OR "
                        "(reversed_at IS NOT NULL AND reversal_reason IS NOT NULL AND reversed_at >= occurred_at)",
                        name="ck_membership_benefit_reversal"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), index=True)
    membership_id: Mapped[str] = mapped_column(ForeignKey("customer_memberships.id"), index=True)
    ticket_line_id: Mapped[str] = mapped_column(ForeignKey("ticket_lines.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    original_unit_price: Mapped[float] = mapped_column(Numeric(10, 2))
    original_total: Mapped[float] = mapped_column(Numeric(10, 2))
    member_unit_price: Mapped[float] = mapped_column(Numeric(10, 2))
    member_total: Mapped[float] = mapped_column(Numeric(10, 2))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str] = mapped_column(String(120))
    actor_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reversed_by: Mapped[str | None] = mapped_column(String(160), nullable=True)
    reversal_reason: Mapped[str | None] = mapped_column(String(240), nullable=True)
