from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), nullable=False, index=True)
    user_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    first_name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    skills: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="available", nullable=False)
