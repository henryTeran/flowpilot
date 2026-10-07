from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base


class EmployeeAbsence(Base):
    __tablename__ = "employee_absences"
    __table_args__ = (
        ForeignKeyConstraint(["institute_id", "employee_id"], ["employees.institute_id", "employees.id"], name="fk_absence_employee_owner"),
        UniqueConstraint("institute_id", "id", name="uq_absence_owner"),
        UniqueConstraint("institute_id", "idempotency_key", name="uq_absence_replay"),
        CheckConstraint("kind IN ('absence','leave')", name="ck_absence_kind"),
        CheckConstraint("end_time > start_time", name="ck_absence_interval"),
        Index("ix_absence_employee_slot", "institute_id", "employee_id", "start_time", "end_time"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(String(80), nullable=False)
    employee_id: Mapped[str] = mapped_column(String(80), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str] = mapped_column(String(240), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AbsenceCancellation(Base):
    __tablename__ = "absence_cancellations"
    __table_args__ = (
        ForeignKeyConstraint(["institute_id", "absence_id"], ["employee_absences.institute_id", "employee_absences.id"], name="fk_absence_cancel_owner"),
        UniqueConstraint("institute_id", "absence_id", name="uq_absence_cancel_original"),
        UniqueConstraint("institute_id", "idempotency_key", name="uq_absence_cancel_replay"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(String(80), nullable=False)
    absence_id: Mapped[str] = mapped_column(String(80), nullable=False)
    reason: Mapped[str] = mapped_column(String(240), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
