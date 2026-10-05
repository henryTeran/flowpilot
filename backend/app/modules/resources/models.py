from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Resource(Base):
    __tablename__ = "resources"
    __table_args__ = (
        UniqueConstraint("institute_id", "name", name="uq_resource_institute_name"),
        CheckConstraint("kind IN ('room','equipment','bed','chair','device')", name="ck_resource_kind"),
        CheckConstraint("status IN ('active','inactive','maintenance')", name="ck_resource_status"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    capabilities: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")


class EmployeeSkill(Base):
    __tablename__ = "employee_skills"
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), nullable=False, index=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), primary_key=True)
    skill_code: Mapped[str] = mapped_column(Text, primary_key=True)


class ServiceRequirement(Base):
    __tablename__ = "service_requirements"
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), primary_key=True)
    service_id: Mapped[str] = mapped_column(ForeignKey("services.id"), primary_key=True)
    skill_code: Mapped[str] = mapped_column(Text, primary_key=True)


class ResourceRequirement(Base):
    __tablename__ = "resource_requirements"
    __table_args__ = (
        CheckConstraint("quantity >= 1 AND quantity <= 10", name="ck_resource_requirement_quantity"),
        CheckConstraint("kind IN ('room','equipment','bed','chair','device')", name="ck_resource_requirement_kind"),
        UniqueConstraint("institute_id", "service_id", "kind", "capability", name="uq_resource_requirement"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), nullable=False, index=True)
    service_id: Mapped[str] = mapped_column(ForeignKey("services.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    capability: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class ResourceConfigurationEvent(Base):
    __tablename__ = "resource_configuration_events"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    target_id: Mapped[str] = mapped_column(String(80), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
