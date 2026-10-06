from datetime import datetime
from decimal import Decimal
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, UniqueConstraint, Index, text
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base


class PaymentIntent(Base):
    __tablename__ = "payment_intents"
    __table_args__ = (
        UniqueConstraint("institute_id", "idempotency_key", name="uq_payment_intent_replay"),
        CheckConstraint("kind IN ('authorize', 'capture', 'refund', 'cancel')", name="ck_payment_intent_kind"),
        CheckConstraint("currency IN ('CHF', 'EUR') AND amount > 0", name="ck_payment_intent_value"),
        CheckConstraint("kind = 'authorize' OR provider_payment_id IS NOT NULL", name="ck_payment_intent_reference"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), index=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("queue_tickets.id"), index=True)
    provider: Mapped[str] = mapped_column(String(80))
    account_id: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(20))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(3))
    provider_payment_id: Mapped[str | None] = mapped_column(String(240), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(120))
    actor_id: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PaymentExecution(Base):
    """Durable authorization seal. Release requires verified domain outcome facts."""
    __tablename__ = "payment_executions"
    __table_args__ = (
        Index("uq_payment_execution_active_ticket", "ticket_id", unique=True,
              sqlite_where=text("released_at IS NULL"), postgresql_where=text("released_at IS NULL")),
    )
    intent_id: Mapped[str] = mapped_column(ForeignKey("payment_intents.id"), primary_key=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("queue_tickets.id"), index=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), index=True)
    sealed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PaymentOutcome(Base):
    """Immutable adapter observations; pending does not release execution."""
    __tablename__ = "payment_outcomes"
    __table_args__ = (
        UniqueConstraint("intent_id", "status", name="uq_payment_outcome_status"),
        CheckConstraint("status IN ('pending', 'authorized', 'failed')", name="ck_payment_outcome_status"),
        CheckConstraint("amount > 0 AND currency IN ('CHF', 'EUR')", name="ck_payment_outcome_value"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    intent_id: Mapped[str] = mapped_column(ForeignKey("payment_executions.intent_id"), index=True)
    status: Mapped[str] = mapped_column(String(20))
    provider_payment_id: Mapped[str] = mapped_column(String(240))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(3))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PaymentReference(Base):
    __tablename__ = "payment_references"
    provider: Mapped[str] = mapped_column(String(80), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    provider_payment_id: Mapped[str] = mapped_column(String(240), primary_key=True)
    intent_id: Mapped[str] = mapped_column(ForeignKey("payment_intents.id"), unique=True)


class ParentOperationExecution(Base):
    """Durable child dispatch seal; parent keeps ticket protection during I/O."""
    __tablename__ = "payment_parent_executions"
    intent_id: Mapped[str] = mapped_column(ForeignKey("payment_intents.id"), primary_key=True)
    parent_intent_id: Mapped[str] = mapped_column(ForeignKey("payment_executions.intent_id"), index=True)
    sealed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ParentOperationOutcome(Base):
    __tablename__ = "payment_parent_outcomes"
    __table_args__ = (
        UniqueConstraint("intent_id", "status", name="uq_payment_parent_outcome_status"),
        CheckConstraint("status IN ('pending', 'failed', 'captured', 'cancelled')", name="ck_payment_parent_outcome_status"),
        CheckConstraint("amount > 0 AND currency IN ('CHF', 'EUR')", name="ck_payment_parent_outcome_value"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    intent_id: Mapped[str] = mapped_column(ForeignKey("payment_parent_executions.intent_id"), index=True)
    status: Mapped[str] = mapped_column(String(20))
    provider_payment_id: Mapped[str] = mapped_column(String(240))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(3))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CaptureApplication(Base):
    __tablename__ = "payment_capture_applications"
    ticket_id: Mapped[str] = mapped_column(ForeignKey("queue_tickets.id"), primary_key=True)
    intent_id: Mapped[str] = mapped_column(ForeignKey("payment_parent_executions.intent_id"), unique=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), index=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"))
    actor_id: Mapped[str] = mapped_column(String(160))
    method: Mapped[str] = mapped_column(String(20))
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RefundExecution(Base):
    __tablename__ = "payment_refund_executions"
    intent_id: Mapped[str] = mapped_column(ForeignKey("payment_intents.id"), primary_key=True)
    capture_intent_id: Mapped[str] = mapped_column(ForeignKey("payment_parent_executions.intent_id"), index=True)
    sealed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RefundOutcome(Base):
    __tablename__ = "payment_refund_outcomes"
    __table_args__ = (
        UniqueConstraint("intent_id", "status", name="uq_payment_refund_outcome_status"),
        CheckConstraint("status IN ('pending', 'failed', 'refunded')", name="ck_payment_refund_outcome_status"),
        CheckConstraint("amount > 0 AND currency IN ('CHF', 'EUR')", name="ck_payment_refund_outcome_value"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    intent_id: Mapped[str] = mapped_column(ForeignKey("payment_refund_executions.intent_id"), index=True)
    status: Mapped[str] = mapped_column(String(20))
    provider_payment_id: Mapped[str] = mapped_column(String(240))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(3))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WebhookReceipt(Base):
    __tablename__ = "payment_webhook_receipts"
    provider: Mapped[str] = mapped_column(String(80), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(240), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), index=True)
    intent_id: Mapped[str] = mapped_column(ForeignKey("payment_intents.id"), index=True)
    status: Mapped[str] = mapped_column(String(20))
    provider_payment_id: Mapped[str] = mapped_column(String(240))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(3))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
