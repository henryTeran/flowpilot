from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, JSON, String, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base


class DemandOriginal(Base):
    __tablename__ = "waitlist_demand_originals"
    __table_args__ = (
        UniqueConstraint("institute_id", "idempotency_key", name="uq_waitlist_demand_replay"),
        Index("ix_waitlist_demand_history", "institute_id", "created_at", "id"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), nullable=False)
    customer_id: Mapped[str] = mapped_column(String(80), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    original: Mapped[dict] = mapped_column(JSON, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
