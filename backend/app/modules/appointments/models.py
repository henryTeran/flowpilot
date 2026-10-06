from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, JSON, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (UniqueConstraint("institute_id", "idempotency_key", name="uq_appointment_institute_idempotency"),
                      UniqueConstraint("checkout_ticket_id", name="uq_appointment_checkout_ticket"),
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
