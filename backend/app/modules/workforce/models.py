from datetime import datetime
from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKeyConstraint, Index, JSON, String, UniqueConstraint
from datetime import date
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base


class EmployeeRebooking(Base):
    __tablename__ = "employee_rebookings"
    __table_args__ = (
        ForeignKeyConstraint(["institute_id", "employee_id"], ["employees.institute_id", "employees.id"], name="fk_rebooking_employee_owner"),
        ForeignKeyConstraint(["institute_id", "session_id"], ["service_sessions.institute_id", "service_sessions.id"], name="fk_rebooking_session_owner"),
        ForeignKeyConstraint(["institute_id", "source_appointment_id"], ["appointments.institute_id", "appointments.id"], name="fk_rebooking_source_booking_owner"),
        ForeignKeyConstraint(["institute_id", "target_appointment_id"], ["appointments.institute_id", "appointments.id"], name="fk_rebooking_target_owner"),
        UniqueConstraint("institute_id", "id", name="uq_rebooking_owner"),
        UniqueConstraint("institute_id", "idempotency_key", name="uq_rebooking_replay"),
        CheckConstraint("(session_id IS NOT NULL AND source_appointment_id IS NULL) OR (session_id IS NULL AND source_appointment_id IS NOT NULL)", name="ck_rebooking_one_source"),
        CheckConstraint("source_appointment_id IS NULL OR source_appointment_id <> target_appointment_id", name="ck_rebooking_no_self"),
        Index("ix_rebooking_employee_recorded", "institute_id", "employee_id", "created_at", "id"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(String(80), nullable=False)
    employee_id: Mapped[str] = mapped_column(String(80), nullable=False)
    session_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source_appointment_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    target_appointment_id: Mapped[str] = mapped_column(String(80), nullable=False)
    source_capture: Mapped[dict] = mapped_column(JSON, nullable=False)
    booking_capture: Mapped[dict] = mapped_column(JSON, nullable=False)
    reason: Mapped[str] = mapped_column(String(240), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RebookingCancellation(Base):
    __tablename__ = "rebooking_cancellations"
    __table_args__ = (
        ForeignKeyConstraint(["institute_id", "rebooking_id"], ["employee_rebookings.institute_id", "employee_rebookings.id"], name="fk_rebooking_cancel_owner"),
        UniqueConstraint("institute_id", "rebooking_id", name="uq_rebooking_cancel_original"),
        UniqueConstraint("institute_id", "idempotency_key", name="uq_rebooking_cancel_replay"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(String(80), nullable=False)
    rebooking_id: Mapped[str] = mapped_column(String(80), nullable=False)
    reason: Mapped[str] = mapped_column(String(240), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EmployeeWorkInterval(Base):
    __tablename__ = "employee_work_intervals"
    __table_args__ = (
        ForeignKeyConstraint(["institute_id", "employee_id"], ["employees.institute_id", "employees.id"], name="fk_work_interval_employee_owner"),
        UniqueConstraint("institute_id", "id", name="uq_work_interval_owner"),
        UniqueConstraint("institute_id", "idempotency_key", name="uq_work_interval_replay"),
        CheckConstraint("end_time > start_time", name="ck_work_interval_positive"),
        Index("ix_work_interval_employee_time", "institute_id", "employee_id", "start_time", "end_time"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(String(80), nullable=False)
    employee_id: Mapped[str] = mapped_column(String(80), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str] = mapped_column(String(240), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WorkIntervalCancellation(Base):
    __tablename__ = "work_interval_cancellations"
    __table_args__ = (
        ForeignKeyConstraint(["institute_id", "work_interval_id"], ["employee_work_intervals.institute_id", "employee_work_intervals.id"], name="fk_work_interval_cancel_owner"),
        UniqueConstraint("institute_id", "work_interval_id", name="uq_work_interval_cancelled_original"),
        UniqueConstraint("institute_id", "idempotency_key", name="uq_work_interval_cancel_replay"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(String(80), nullable=False)
    work_interval_id: Mapped[str] = mapped_column(String(80), nullable=False)
    reason: Mapped[str] = mapped_column(String(240), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EmployeeObjective(Base):
    __tablename__ = "employee_objectives"
    __table_args__ = (
        ForeignKeyConstraint(["institute_id", "employee_id"], ["employees.institute_id", "employees.id"], name="fk_objective_employee_owner"),
        UniqueConstraint("institute_id", "id", name="uq_objective_owner"),
        UniqueConstraint("institute_id", "idempotency_key", name="uq_objective_replay"),
        CheckConstraint("CAST(target AS NUMERIC) > 0 AND period_end > period_start AND last_day >= first_day", name="ck_objective_period_target"),
        CheckConstraint("(metric = 'closed_attributed_gross' AND currency IS NOT NULL AND currency IN ('CHF', 'EUR')) OR (metric = 'completed_sessions' AND currency IS NULL AND CAST(target AS NUMERIC) = CAST(CAST(target AS NUMERIC) AS BIGINT))", name="ck_objective_metric_unit"),
        Index("ix_objective_employee_period", "institute_id", "employee_id", "period_start", "period_end"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(String(80), nullable=False)
    employee_id: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    metric: Mapped[str] = mapped_column(String(40), nullable=False)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    target: Mapped[str] = mapped_column(String(32), nullable=False)
    first_day: Mapped[date] = mapped_column(Date, nullable=False)
    last_day: Mapped[date] = mapped_column(Date, nullable=False)
    timezone: Mapped[str] = mapped_column(String(80), nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str] = mapped_column(String(240), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ObjectiveCancellation(Base):
    __tablename__ = "objective_cancellations"
    __table_args__ = (
        ForeignKeyConstraint(["institute_id", "objective_id"], ["employee_objectives.institute_id", "employee_objectives.id"], name="fk_objective_cancel_owner"),
        UniqueConstraint("institute_id", "objective_id", name="uq_objective_cancelled_original"),
        UniqueConstraint("institute_id", "idempotency_key", name="uq_objective_cancel_replay"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(String(80), nullable=False)
    objective_id: Mapped[str] = mapped_column(String(80), nullable=False)
    reason: Mapped[str] = mapped_column(String(240), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EmployeeSkillChange(Base):
    __tablename__ = "employee_skill_changes"
    __table_args__ = (
        ForeignKeyConstraint(["institute_id", "employee_id"], ["employees.institute_id", "employees.id"], name="fk_skill_change_employee_owner"),
        UniqueConstraint("institute_id", "idempotency_key", name="uq_skill_change_replay"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(String(80), nullable=False)
    employee_id: Mapped[str] = mapped_column(String(80), nullable=False)
    expected_skills: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    skills: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    reason: Mapped[str] = mapped_column(String(240), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


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


class EmployeeCertification(Base):
    __tablename__ = "employee_certifications"
    __table_args__ = (
        ForeignKeyConstraint(["institute_id", "employee_id"], ["employees.institute_id", "employees.id"], name="fk_certification_employee_owner"),
        UniqueConstraint("institute_id", "id", name="uq_certification_owner"),
        UniqueConstraint("institute_id", "idempotency_key", name="uq_certification_replay"),
        CheckConstraint("valid_until IS NULL OR valid_until > valid_from", name="ck_certification_interval"),
        Index("ix_certification_employee_code", "institute_id", "employee_id", "code", "valid_from", "valid_until"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(String(80), nullable=False)
    employee_id: Mapped[str] = mapped_column(String(80), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    issuer: Mapped[str] = mapped_column(String(120), nullable=False)
    reference: Mapped[str] = mapped_column(String(160), nullable=False)
    issued_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[str] = mapped_column(String(240), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CertificationRevocation(Base):
    __tablename__ = "certification_revocations"
    __table_args__ = (
        ForeignKeyConstraint(["institute_id", "certification_id"], ["employee_certifications.institute_id", "employee_certifications.id"], name="fk_certification_revocation_owner"),
        UniqueConstraint("institute_id", "certification_id", name="uq_certification_revoked_original"),
        UniqueConstraint("institute_id", "idempotency_key", name="uq_certification_revocation_replay"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(String(80), nullable=False)
    certification_id: Mapped[str] = mapped_column(String(80), nullable=False)
    reason: Mapped[str] = mapped_column(String(240), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
