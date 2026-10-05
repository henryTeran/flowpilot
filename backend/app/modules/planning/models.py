from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class ServiceSession(Base):
    __tablename__ = "service_sessions"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    ticket_line_id: Mapped[str | None] = mapped_column(ForeignKey("ticket_lines.id"), nullable=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), nullable=False, index=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    service_id: Mapped[str] = mapped_column(ForeignKey("services.id"), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    planned_end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    real_end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="planned", nullable=False, index=True)


class SessionExtension(Base):
    __tablename__ = "session_extensions"
    __table_args__ = (
        UniqueConstraint("session_id", "idempotency_key", name="uq_session_extension_replay"),
        CheckConstraint("minutes IN (5, 10, 15, 20, 30, 45, 60)", name="ck_session_extension_minutes"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("service_sessions.id"), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resulting_end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    requested_by: Mapped[str | None] = mapped_column(String(160), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
