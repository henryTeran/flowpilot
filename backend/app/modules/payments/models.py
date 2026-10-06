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
