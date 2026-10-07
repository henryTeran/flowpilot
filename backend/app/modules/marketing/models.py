from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base

class AudienceOriginal(Base):
    __tablename__="marketing_audience_originals"
    __table_args__=(UniqueConstraint("institute_id","id",name="uq_marketing_audience_owner"),UniqueConstraint("institute_id","idempotency_key",name="uq_marketing_audience_replay"))
    id:Mapped[str]=mapped_column(String(80),primary_key=True)
    institute_id:Mapped[str]=mapped_column(ForeignKey("institutes.id"),nullable=False)
    actor_id:Mapped[str]=mapped_column(String(160),nullable=False)
    reason:Mapped[str]=mapped_column(String(240),nullable=False)
    idempotency_key:Mapped[str]=mapped_column(String(120),nullable=False)
    captured_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    request:Mapped[dict]=mapped_column(JSON,nullable=False)
    summary:Mapped[dict]=mapped_column(JSON,nullable=False)

class AudiencePage(Base):
    __tablename__="marketing_audience_pages"
    __table_args__=(ForeignKeyConstraint(["institute_id","capture_id"],["marketing_audience_originals.institute_id","marketing_audience_originals.id"],name="fk_marketing_audience_page_owner"),CheckConstraint("page_index >= 0",name="ck_marketing_audience_page_index"))
    institute_id:Mapped[str]=mapped_column(String(80),primary_key=True)
    capture_id:Mapped[str]=mapped_column(String(80),primary_key=True)
    page_index:Mapped[int]=mapped_column(Integer,primary_key=True)
    observation:Mapped[dict]=mapped_column(JSON,nullable=False)
