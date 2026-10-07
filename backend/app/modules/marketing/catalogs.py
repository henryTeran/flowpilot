"""Bounded owned selection catalogs; current heads are joined on complete scope."""
from typing import Generic,TypeVar
from pydantic import model_validator
from sqlalchemy import select,func,and_
from app.modules.crm.metrics import Fact,Identifier,Count
from app.modules.marketing import audience_originals,templates,campaign_originals
from app.modules.marketing.models import AudienceOriginal,TemplateOriginal,TemplateHead,CampaignOriginal,CampaignHead
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import business_error
T=TypeVar("T")
class Page(Fact,Generic[T]):
    institute_id: Identifier
    total: Count
    offset: Count
    limit: Count
    items: tuple[T,...]
    @model_validator(mode="after")
    def bounded_complete_page(self):
        if not 1<=self.limit<=50 or len(self.items)!=min(self.limit,max(0,self.total-self.offset)):
            raise ValueError("Catalog total/bounds and returned page must agree")
        return self
def bounds(db,institute,offset,limit):
    if type(offset) is not int or offset<0 or type(limit) is not int or not 1<=limit<=50:raise business_error("Bounded catalog page required")
    lock_institute(db,institute)
def audiences(db,institute,offset=0,limit=20):
    bounds(db,institute,offset,limit)
    scope=AudienceOriginal.institute_id==institute
    total=db.scalar(select(func.count()).select_from(AudienceOriginal).where(scope))
    rows=db.scalars(select(AudienceOriginal).where(scope).order_by(AudienceOriginal.captured_at.desc(),AudienceOriginal.id).offset(offset).limit(limit))
    return Page[audience_originals.Original](institute_id=institute,total=total,offset=offset,limit=limit,items=tuple(audience_originals.receipt(row) for row in rows))
def templates_current(db,institute,offset=0,limit=20):
    bounds(db,institute,offset,limit)
    scope=TemplateHead.institute_id==institute
    total=db.scalar(select(func.count()).select_from(TemplateHead).where(scope))
    rows=db.execute(select(TemplateHead,TemplateOriginal).outerjoin(TemplateOriginal,and_(TemplateOriginal.institute_id==TemplateHead.institute_id,TemplateOriginal.template_id==TemplateHead.template_id,TemplateOriginal.id==TemplateHead.original_id)).where(scope).order_by(TemplateHead.template_id).offset(offset).limit(limit)).all()
    if any(row is None for _,row in rows):raise business_error("Selected template catalog scope is incoherent")
    return Page[templates.Original](institute_id=institute,total=total,offset=offset,limit=limit,items=tuple(templates.receipt(row) for _,row in rows))
def campaigns_current(db,institute,offset=0,limit=20):
    bounds(db,institute,offset,limit)
    scope=CampaignHead.institute_id==institute
    total=db.scalar(select(func.count()).select_from(CampaignHead).where(scope))
    rows=db.execute(select(CampaignHead,CampaignOriginal).outerjoin(CampaignOriginal,and_(CampaignOriginal.institute_id==CampaignHead.institute_id,CampaignOriginal.campaign_id==CampaignHead.campaign_id,CampaignOriginal.id==CampaignHead.original_id)).where(scope).order_by(CampaignHead.campaign_id).offset(offset).limit(limit)).all()
    if any(row is None for _,row in rows):raise business_error("Selected campaign catalog scope is incoherent")
    return Page[campaign_originals.Original](institute_id=institute,total=total,offset=offset,limit=limit,items=tuple(campaign_originals.receipt(row) for _,row in rows))
