from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class PackagePlan(Base):
    __tablename__ = "package_plans"
    __table_args__ = (
        CheckConstraint("sessions > 0 AND valid_days > 0", name="ck_package_plan_terms"),
        UniqueConstraint("institute_id", "idempotency_key", name="uq_package_plan_creation_replay"),
        CheckConstraint("(idempotency_key IS NULL AND creation_fingerprint IS NULL) OR "
                        "(idempotency_key IS NOT NULL AND creation_fingerprint IS NOT NULL)",
                        name="ck_package_plan_creation_replay"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), index=True)
    service_id: Mapped[str] = mapped_column(ForeignKey("services.id"))
    name: Mapped[str] = mapped_column(String(120))
    sessions: Mapped[int] = mapped_column(Integer)
    valid_days: Mapped[int] = mapped_column(Integer)
    idempotency_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    creation_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)


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
        Index("uq_package_redeem_active_line", "ticket_line_id", unique=True,
              sqlite_where=text("reversed_at IS NULL"), postgresql_where=text("reversed_at IS NULL")),
        CheckConstraint("sessions > 0", name="ck_package_redeem_sessions"),
        CheckConstraint("(reversed_at IS NULL AND reversed_by IS NULL AND reversal_reason IS NULL) OR "
                        "(reversed_at IS NOT NULL AND reversal_reason IS NOT NULL AND reversed_at >= occurred_at)",
                        name="ck_package_reversal_facts"),
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
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reversed_by: Mapped[str | None] = mapped_column(String(160), nullable=True)
    reversal_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
