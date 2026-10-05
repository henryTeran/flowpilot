from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class PackagePlan(Base):
    __tablename__ = "package_plans"
    __table_args__ = (CheckConstraint("sessions > 0 AND valid_days > 0", name="ck_package_plan_terms"),)
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), index=True)
    service_id: Mapped[str] = mapped_column(ForeignKey("services.id"))
    name: Mapped[str] = mapped_column(String(120))
    sessions: Mapped[int] = mapped_column(Integer)
    valid_days: Mapped[int] = mapped_column(Integer)


class CustomerPackage(Base):
    __tablename__ = "customer_packages"
    __table_args__ = (
        UniqueConstraint("institute_id", "idempotency_key", name="uq_package_issue_replay"),
        CheckConstraint("sessions > 0 AND consumed >= 0 AND consumed <= sessions", name="ck_package_balance"),
        CheckConstraint("expires_at > issued_at", name="ck_package_expiry"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), index=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey("package_plans.id"))
    customer_id: Mapped[str] = mapped_column(String(80), index=True)
    service_id: Mapped[str] = mapped_column(ForeignKey("services.id"))
    name: Mapped[str] = mapped_column(String(120))
    sessions: Mapped[int] = mapped_column(Integer)
    consumed: Mapped[int] = mapped_column(Integer, default=0)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str] = mapped_column(String(120))
    actor_id: Mapped[str | None] = mapped_column(String(160), nullable=True)


class PackageRedemption(Base):
    __tablename__ = "package_redemptions"
    __table_args__ = (
        UniqueConstraint("institute_id", "idempotency_key", name="uq_package_redeem_replay"),
        UniqueConstraint("ticket_line_id", name="uq_package_redeem_line"),
        CheckConstraint("sessions > 0", name="ck_package_redeem_sessions"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), index=True)
    package_id: Mapped[str] = mapped_column(ForeignKey("customer_packages.id"), index=True)
    ticket_line_id: Mapped[str] = mapped_column(ForeignKey("ticket_lines.id"))
    sessions: Mapped[int] = mapped_column(Integer)
    original_unit_price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    original_total: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str] = mapped_column(String(120))
    actor_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
