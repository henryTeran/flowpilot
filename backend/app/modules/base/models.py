from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, JSON, String, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base


class PlanOriginal(Base):
    __tablename__ = "base_plan_originals"
    __table_args__ = (
        UniqueConstraint("institute_id", "idempotency_key", name="uq_base_plan_replay"),
        Index("ix_base_plan_history", "institute_id", "created_at", "id"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    original: Mapped[dict] = mapped_column(JSON, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)


class SensitiveOperationOriginal(Base):
    __tablename__ = "base_sensitive_operation_originals"
    __table_args__ = (
        UniqueConstraint("institute_id", "idempotency_key", name="uq_base_sensitive_operation_replay"),
        Index("ix_base_sensitive_operation_history", "institute_id", "created_at", "id"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    original: Mapped[dict] = mapped_column(JSON, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)


class ApprovalOriginal(Base):
    __tablename__ = "base_approval_originals"
    __table_args__ = (
        UniqueConstraint("institute_id", "idempotency_key", name="uq_base_approval_replay"),
        UniqueConstraint("operation_id", "previous_id", name="uq_base_approval_successor"),
        Index("ix_base_approval_history", "institute_id", "operation_id", "created_at", "id"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), nullable=False)
    operation_id: Mapped[str] = mapped_column(ForeignKey("base_sensitive_operation_originals.id"), nullable=False)
    previous_id: Mapped[str | None] = mapped_column(ForeignKey("base_approval_originals.id"), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    original: Mapped[dict] = mapped_column(JSON, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)


class ExecutionOriginal(Base):
    __tablename__ = "base_execution_originals"
    __table_args__ = (
        UniqueConstraint("institute_id", "idempotency_key", name="uq_base_execution_replay"),
        UniqueConstraint("operation_id", name="uq_base_execution_operation"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), nullable=False)
    operation_id: Mapped[str] = mapped_column(ForeignKey("base_sensitive_operation_originals.id"), nullable=False)
    approval_id: Mapped[str] = mapped_column(ForeignKey("base_approval_originals.id"), nullable=False)
    booking_event_id: Mapped[str] = mapped_column(ForeignKey("booking_events.id"), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    original: Mapped[dict] = mapped_column(JSON, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
