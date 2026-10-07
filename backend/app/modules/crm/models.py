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


class BirthdayPolicyOriginal(Base):
    __tablename__ = "crm_birthday_policy_originals"
    __table_args__ = (
        UniqueConstraint("institute_id", "id", name="uq_crm_birthday_policy_owner"),
        UniqueConstraint("institute_id", "idempotency_key", name="uq_crm_birthday_policy_replay"),
        ForeignKeyConstraint(["institute_id", "previous_policy_id"],
            ["crm_birthday_policy_originals.institute_id", "crm_birthday_policy_originals.id"], name="fk_crm_birthday_policy_previous_owner"),)
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), nullable=False)
    previous_policy_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    policy: Mapped[dict] = mapped_column(JSON, nullable=False)
    reason: Mapped[str] = mapped_column(String(240), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BirthdayPolicyHead(Base):
    __tablename__ = "crm_birthday_policy_heads"
    __table_args__ = (ForeignKeyConstraint(["institute_id", "policy_id"],
        ["crm_birthday_policy_originals.institute_id", "crm_birthday_policy_originals.id"], name="fk_crm_birthday_policy_head_owner"),)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), primary_key=True)
    policy_id: Mapped[str] = mapped_column(String(80), nullable=False)



class LifecycleOriginal(Base):
    __tablename__ = "crm_lifecycle_originals"
    __table_args__ = (
        UniqueConstraint("institute_id", "customer_id", "id", name="uq_crm_lifecycle_owner"),
        UniqueConstraint("institute_id", "customer_id", "idempotency_key", name="uq_crm_lifecycle_replay"),
        ForeignKeyConstraint(["institute_id", "customer_id", "previous_id"],
            ["crm_lifecycle_originals.institute_id", "crm_lifecycle_originals.customer_id", "crm_lifecycle_originals.id"], name="fk_crm_lifecycle_previous_owner"),)
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), nullable=False)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), nullable=False)
    previous_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    declaration: Mapped[dict] = mapped_column(JSON, nullable=False)
    reason: Mapped[str] = mapped_column(String(240), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LifecycleHead(Base):
    __tablename__ = "crm_lifecycle_heads"
    __table_args__ = (ForeignKeyConstraint(["institute_id", "customer_id", "original_id"],
        ["crm_lifecycle_originals.institute_id", "crm_lifecycle_originals.customer_id", "crm_lifecycle_originals.id"], name="fk_crm_lifecycle_head_owner"),)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), primary_key=True)
    original_id: Mapped[str] = mapped_column(String(80), nullable=False)


class AutomationPolicyOriginal(Base):
    __tablename__ = "crm_automation_policy_originals"
    __table_args__ = (
        UniqueConstraint("institute_id", "id", name="uq_crm_automation_policy_owner"),
        UniqueConstraint("institute_id", "idempotency_key", name="uq_crm_automation_policy_replay"),
        ForeignKeyConstraint(["institute_id", "previous_policy_id"],
            ["crm_automation_policy_originals.institute_id", "crm_automation_policy_originals.id"], name="fk_crm_automation_policy_previous_owner"),)
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), nullable=False)
    previous_policy_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    policy: Mapped[dict] = mapped_column(JSON, nullable=False)
    reason: Mapped[str] = mapped_column(String(240), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AutomationPolicyHead(Base):
    __tablename__ = "crm_automation_policy_heads"
    __table_args__ = (ForeignKeyConstraint(["institute_id", "policy_id"],
        ["crm_automation_policy_originals.institute_id", "crm_automation_policy_originals.id"], name="fk_crm_automation_policy_head_owner"),)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), primary_key=True)
    policy_id: Mapped[str] = mapped_column(String(80), nullable=False)


class EventCaptureOriginal(Base):
    __tablename__ = "crm_event_capture_originals"
    __table_args__ = (
        UniqueConstraint("institute_id", "customer_id", "id", name="uq_crm_event_capture_owner"),
        UniqueConstraint("institute_id", "customer_id", "idempotency_key", name="uq_crm_event_capture_replay"),)
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), nullable=False)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    reason: Mapped[str] = mapped_column(String(240), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[dict] = mapped_column(JSON, nullable=False)


class EventRevision(Base):
    __tablename__ = "crm_event_revisions"
    __table_args__ = (
        UniqueConstraint("institute_id", "customer_id", "event_key", "id", name="uq_crm_event_revision_owner"),
        ForeignKeyConstraint(["institute_id", "customer_id", "capture_id"],
            ["crm_event_capture_originals.institute_id", "crm_event_capture_originals.customer_id", "crm_event_capture_originals.id"], name="fk_crm_event_revision_capture_owner"),
        ForeignKeyConstraint(["institute_id", "customer_id", "event_key", "previous_id"],
            ["crm_event_revisions.institute_id", "crm_event_revisions.customer_id", "crm_event_revisions.event_key", "crm_event_revisions.id"], name="fk_crm_event_revision_previous_owner"),)
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), nullable=False)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), nullable=False)
    event_key: Mapped[str] = mapped_column(String(80), nullable=False)
    capture_id: Mapped[str] = mapped_column(String(80), nullable=False)
    previous_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    decision: Mapped[dict] = mapped_column(JSON, nullable=False)


class EventHead(Base):
    __tablename__ = "crm_event_heads"
    __table_args__ = (ForeignKeyConstraint(["institute_id", "customer_id", "event_key", "revision_id"],
        ["crm_event_revisions.institute_id", "crm_event_revisions.customer_id", "crm_event_revisions.event_key", "crm_event_revisions.id"], name="fk_crm_event_head_owner"),)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), primary_key=True)
    event_key: Mapped[str] = mapped_column(String(80), primary_key=True)
    revision_id: Mapped[str] = mapped_column(String(80), nullable=False)
