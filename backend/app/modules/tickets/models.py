from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class QueueTicket(Base):
    __tablename__ = "queue_tickets"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), nullable=False, index=True)
    ticket_number: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    customer_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    subscription_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="waiting", nullable=False, index=True)
    arrival_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    estimated_start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Collaboratrice à qui le ticket est affecté pendant la prestation.
    assigned_employee_id: Mapped[str | None] = mapped_column(String(80), nullable=True)

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


class TicketLine(Base):
    __tablename__ = "ticket_lines"

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
