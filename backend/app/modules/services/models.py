from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class ServiceCategory(Base):
    __tablename__ = "service_categories"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    parent_id: Mapped[str | None] = mapped_column(String(80), nullable=True)


class Service(Base):
    __tablename__ = "services"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    category_id: Mapped[str] = mapped_column(ForeignKey("service_categories.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    duration_min: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_member: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    price_passage: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    requires_machine: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    requires_appointment: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)
