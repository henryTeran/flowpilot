from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class QueueTicket(Base):
    __tablename__ = "queue_tickets"
    __table_args__ = (
        Index("uq_queue_ticket_owner", "institute_id", "id", unique=True),
        Index("ix_queue_ticket_inst_status", "institute_id", "status"),
        UniqueConstraint("institute_id", "idempotency_key", name="uq_queue_ticket_institute_idempotency"),
        CheckConstraint("currency IS NULL OR currency IN ('CHF', 'EUR')", name="ck_ticket_currency"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), nullable=False, index=True)
    ticket_number: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    creation_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    customer_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    subscription_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="waiting", nullable=False, index=True)
    arrival_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    estimated_start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Collaboratrice à qui le ticket est affecté pendant la prestation.
    assigned_employee_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Collaboratrice / réception qui a créé le ticket après l'écran "Je m'identifie".
    created_by_id: Mapped[str | None] = mapped_column(String(80), nullable=True)

    # Collaboratrice qui s'identifie au moment de l'encaissement.
    checkout_employee_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    checkout_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Collaboratrice qui valide le paiement final. En général la même que checkout_employee_id.
    paid_employee_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payment_method: Mapped[str | None] = mapped_column(String(40), nullable=True)
    total_amount: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)


class TicketCurrencyFact(Base):
    __tablename__ = "ticket_currency_facts"
    __table_args__ = (
        UniqueConstraint("ticket_id", name="uq_ticket_currency_fact"),
        CheckConstraint("currency IN ('CHF', 'EUR')", name="ck_ticket_currency_fact"),
        CheckConstraint("source IN ('institute_settings', 'cashier_confirmation')", name="ck_ticket_currency_source"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), index=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("queue_tickets.id"))
    currency: Mapped[str] = mapped_column(String(3))
    source: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(String(240))
    actor_id: Mapped[str] = mapped_column(String(160))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class QueueEvent(Base):
    __tablename__ = "queue_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), nullable=False, index=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("queue_tickets.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    previous_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    employee_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TicketLine(Base):
    __tablename__ = "ticket_lines"
    __table_args__ = (
        Index("uq_ticket_line_ticket_owner", "ticket_id", "id", unique=True),
        CheckConstraint("(invoice_removed_at IS NULL AND invoice_removed_by_actor IS NULL AND invoice_removal_reason IS NULL) OR (invoice_removed_at IS NOT NULL AND invoice_removed_by_actor IS NOT NULL AND length(trim(invoice_removed_by_actor)) > 0 AND invoice_removal_reason IS NOT NULL AND invoice_removal_reason = 'not_performed')", name="ck_ticket_line_invoice_removal"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("queue_tickets.id"), nullable=False, index=True)
    service_id: Mapped[str] = mapped_column(ForeignKey("services.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    unit_price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    total: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    revenue_category: Mapped[str] = mapped_column(String(40), default="care", nullable=False)

    # Collaboratrice qui a réellement réalisé la ligne de prestation.
    performed_by_employee_id: Mapped[str | None] = mapped_column(String(80), nullable=True)

    # Original execution/billing terms remain intact after an unpaid correction.
    invoice_removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invoice_removed_by_actor: Mapped[str | None] = mapped_column(String(160), nullable=True)
    invoice_removal_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
