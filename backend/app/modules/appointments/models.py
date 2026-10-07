from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, ForeignKeyConstraint, String, JSON, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (UniqueConstraint("institute_id", "idempotency_key", name="uq_appointment_institute_idempotency"),
                      UniqueConstraint("checkout_ticket_id", name="uq_appointment_checkout_ticket"),
                      Index("ix_appointment_inst_status_actual_end", "institute_id", "status", "actual_end_time"),
                      Index("ix_appointment_inst_status_slot", "institute_id", "status", "start_time", "end_time"),
                      Index("uq_appointment_owner", "institute_id", "id", unique=True))

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    creation_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    checkout_ticket_id: Mapped[str | None] = mapped_column(ForeignKey("queue_tickets.id", name="fk_appointment_checkout_ticket"), nullable=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), nullable=False, index=True)
    service_id: Mapped[str] = mapped_column(ForeignKey("services.id"), nullable=False, index=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    customer_name: Mapped[str] = mapped_column(String(160), nullable=False)
    customer_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    booked_start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    booked_end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="scheduled", nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)


class BookingEvent(Base):
    __tablename__ = "booking_events"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), nullable=False, index=True)
    appointment_id: Mapped[str] = mapped_column(ForeignKey("appointments.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    before: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after: Mapped[dict] = mapped_column(JSON, nullable=False)
    price_reference: Mapped[dict | None] = mapped_column(JSON(none_as_null=True), nullable=True)


class AppointmentInvoiceLine(Base):
    """Original invoice line created by the appointment completion transaction."""
    __tablename__ = "appointment_invoice_lines"
    __table_args__ = (
        ForeignKeyConstraint(["institute_id", "appointment_id"], ["appointments.institute_id", "appointments.id"], name="fk_appointment_invoice_source_owner"),
        ForeignKeyConstraint(["institute_id", "ticket_id"], ["queue_tickets.institute_id", "queue_tickets.id"], name="fk_appointment_invoice_ticket_owner"),
        ForeignKeyConstraint(["ticket_id", "ticket_line_id"], ["ticket_lines.ticket_id", "ticket_lines.id"], name="fk_appointment_invoice_line_owner"),
        UniqueConstraint("ticket_id", name="uq_appointment_invoice_ticket"),
        UniqueConstraint("ticket_line_id", name="uq_appointment_invoice_line"),
    )
    appointment_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), nullable=False, index=True)
    ticket_id: Mapped[str] = mapped_column(String(80), nullable=False)
    ticket_line_id: Mapped[str] = mapped_column(String(80), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
