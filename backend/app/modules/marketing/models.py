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

class TemplateOriginal(Base):
    __tablename__="marketing_template_originals"
    __table_args__=(UniqueConstraint("institute_id","id",name="uq_marketing_template_owner"),UniqueConstraint("institute_id","template_id","id",name="uq_marketing_template_revision"),UniqueConstraint("institute_id","idempotency_key",name="uq_marketing_template_replay"),ForeignKeyConstraint(["institute_id","template_id","previous_id"],["marketing_template_originals.institute_id","marketing_template_originals.template_id","marketing_template_originals.id"],name="fk_marketing_template_previous"))
    id:Mapped[str]=mapped_column(String(80),primary_key=True)
    institute_id:Mapped[str]=mapped_column(ForeignKey("institutes.id"),nullable=False)
    template_id:Mapped[str]=mapped_column(String(80),nullable=False)
    previous_id:Mapped[str|None]=mapped_column(String(80),nullable=True)
    actor_id:Mapped[str]=mapped_column(String(160),nullable=False)
    reason:Mapped[str]=mapped_column(String(240),nullable=False)
    idempotency_key:Mapped[str]=mapped_column(String(120),nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    request:Mapped[dict]=mapped_column(JSON,nullable=False)
    content:Mapped[dict]=mapped_column(JSON,nullable=False)

class TemplateHead(Base):
    __tablename__="marketing_template_heads"
    __table_args__=(ForeignKeyConstraint(["institute_id","template_id","original_id"],["marketing_template_originals.institute_id","marketing_template_originals.template_id","marketing_template_originals.id"],name="fk_marketing_template_head"),)
    institute_id:Mapped[str]=mapped_column(String(80),primary_key=True)
    template_id:Mapped[str]=mapped_column(String(80),primary_key=True)
    original_id:Mapped[str]=mapped_column(String(80),nullable=False)

class CampaignOriginal(Base):
    __tablename__="marketing_campaign_originals"
    __table_args__=(UniqueConstraint("institute_id","campaign_id","id",name="uq_marketing_campaign_revision"),UniqueConstraint("institute_id","idempotency_key",name="uq_marketing_campaign_replay"),ForeignKeyConstraint(["institute_id","campaign_id","previous_id"],["marketing_campaign_originals.institute_id","marketing_campaign_originals.campaign_id","marketing_campaign_originals.id"],name="fk_marketing_campaign_previous"),ForeignKeyConstraint(["institute_id","audience_id"],["marketing_audience_originals.institute_id","marketing_audience_originals.id"],name="fk_marketing_campaign_audience"),ForeignKeyConstraint(["institute_id","template_original_id"],["marketing_template_originals.institute_id","marketing_template_originals.id"],name="fk_marketing_campaign_template"))
    id:Mapped[str]=mapped_column(String(80),primary_key=True)
    institute_id:Mapped[str]=mapped_column(ForeignKey("institutes.id"),nullable=False)
    campaign_id:Mapped[str]=mapped_column(String(80),nullable=False)
    previous_id:Mapped[str|None]=mapped_column(String(80),nullable=True)
    audience_id:Mapped[str]=mapped_column(String(80),nullable=False)
    template_original_id:Mapped[str|None]=mapped_column(String(80),nullable=True)
    actor_id:Mapped[str]=mapped_column(String(160),nullable=False)
    reason:Mapped[str]=mapped_column(String(240),nullable=False)
    idempotency_key:Mapped[str]=mapped_column(String(120),nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    request:Mapped[dict]=mapped_column(JSON,nullable=False)
    revision:Mapped[dict]=mapped_column(JSON,nullable=False)

class CampaignHead(Base):
    __tablename__="marketing_campaign_heads"
    __table_args__=(ForeignKeyConstraint(["institute_id","campaign_id","original_id"],["marketing_campaign_originals.institute_id","marketing_campaign_originals.campaign_id","marketing_campaign_originals.id"],name="fk_marketing_campaign_head"),)
    institute_id:Mapped[str]=mapped_column(String(80),primary_key=True)
    campaign_id:Mapped[str]=mapped_column(String(80),primary_key=True)
    original_id:Mapped[str]=mapped_column(String(80),nullable=False)
