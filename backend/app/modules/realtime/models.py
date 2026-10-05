from sqlalchemy import BigInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class PlanningRevision(Base):
    __tablename__ = "planning_revisions"
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), primary_key=True)
    revision: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
