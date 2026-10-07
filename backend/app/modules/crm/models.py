from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, ForeignKeyConstraint, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base


class SegmentPolicyOriginal(Base):
    __tablename__ = "crm_segment_policy_originals"
    __table_args__ = (
        UniqueConstraint("institute_id", "id", name="uq_crm_policy_owner"),
        UniqueConstraint("institute_id", "idempotency_key", name="uq_crm_policy_replay"),
        ForeignKeyConstraint(["institute_id", "previous_policy_id"],
            ["crm_segment_policy_originals.institute_id", "crm_segment_policy_originals.id"], name="fk_crm_policy_previous_owner"),)
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), nullable=False)
    previous_policy_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    policy: Mapped[dict] = mapped_column(JSON, nullable=False)
    reason: Mapped[str] = mapped_column(String(240), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SegmentPolicyHead(Base):
    __tablename__ = "crm_segment_policy_heads"
    __table_args__ = (ForeignKeyConstraint(["institute_id", "policy_id"],
        ["crm_segment_policy_originals.institute_id", "crm_segment_policy_originals.id"], name="fk_crm_policy_head_owner"),)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), primary_key=True)
    policy_id: Mapped[str] = mapped_column(String(80), nullable=False)


class LifetimeOriginal(Base):
    __tablename__ = "crm_lifetime_originals"
    __table_args__ = (
        UniqueConstraint("institute_id", "customer_id", "id", name="uq_crm_lifetime_owner"),
        UniqueConstraint("institute_id", "customer_id", "idempotency_key", name="uq_crm_lifetime_replay"),
        ForeignKeyConstraint(["institute_id", "customer_id", "previous_id"],
            ["crm_lifetime_originals.institute_id", "crm_lifetime_originals.customer_id", "crm_lifetime_originals.id"], name="fk_crm_lifetime_previous_owner"),)
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), nullable=False)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), nullable=False)
    previous_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    assumptions: Mapped[dict] = mapped_column(JSON, nullable=False)
    reason: Mapped[str] = mapped_column(String(240), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LifetimeHead(Base):
    __tablename__ = "crm_lifetime_heads"
    __table_args__ = (ForeignKeyConstraint(["institute_id", "customer_id", "original_id"],
        ["crm_lifetime_originals.institute_id", "crm_lifetime_originals.customer_id", "crm_lifetime_originals.id"], name="fk_crm_lifetime_head_owner"),)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), primary_key=True)
    original_id: Mapped[str] = mapped_column(String(80), nullable=False)
