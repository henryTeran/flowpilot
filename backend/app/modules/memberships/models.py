from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
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
