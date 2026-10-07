"""Signed retained campaign drafting/review/approval; no provider dispatch."""
from typing import Literal
from pydantic import model_validator
from sqlalchemy import select,func
from app.modules.crm.metrics import Fact,Identifier,Count
from app.modules.crm.policies import Reason,Key
from app.modules.marketing import campaigns,audience_originals,templates
from app.modules.marketing.models import CampaignOriginal,CampaignHead
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import business_error,not_found
from app.shared.ids import new_id
from app.shared.time import utcnow,explicit_utc_instant

class Content(Fact):
    channel: Literal["sms","email","push"]
    origin: Literal["human","ai"]
    subject: str | None
    body: str
    audience_id: Identifier
    template_original_id: Identifier | None
    @model_validator(mode="after")
    def content_shape(self):
        templates.Content(name="Campaign content",channel=self.channel,origin=self.origin,subject=self.subject,body=self.body)
        return self
class Request(Fact):
    action: Literal["create","edit","review","approve"]
    campaign_id: Identifier | None
    expected_revision_id: Identifier | None
    content: Content | None
    reason: Reason
    idempotency_key: Key
    @model_validator(mode="after")
    def target(self):
        if self.action=="create":valid=self.campaign_id is None and self.expected_revision_id is None and self.content is not None
        else:valid=self.campaign_id is not None and self.expected_revision_id is not None and ((self.action=="edit")== (self.content is not None))
        if not valid:raise ValueError("Explicit new campaign or selected revision/content required")
        return self
class Original(Fact):
    request: Request
    revision: campaigns.CampaignRevision

def receipt(row):
    request=Request.model_validate(row.request);revision=campaigns.CampaignRevision.model_validate(row.revision)
    if (revision.id,revision.institute_id,revision.campaign_id,revision.previous_id,revision.actor_id,revision.reason,revision.created_at)!=(row.id,row.institute_id,row.campaign_id,row.previous_id,row.actor_id,row.reason,explicit_utc_instant(row.created_at)) or request.reason!=row.reason or request.idempotency_key!=row.idempotency_key or request.expected_revision_id!=row.previous_id or request.campaign_id is not None and request.campaign_id!=row.campaign_id or revision.content.audience.id!=row.audience_id or revision.content.template_original_id!=row.template_original_id:
        raise business_error("Campaign original scope/actor/terms are incoherent")
    expected={"create":"DRAFT","edit":"DRAFT","review":"REVIEW","approve":"APPROVE"}[request.action]
    if revision.state!=expected:raise business_error("Campaign original stage is incoherent")
    c=request.content
    if c is not None and (c.channel,c.origin,c.subject,c.body,c.audience_id,c.template_original_id)!=(revision.content.channel,revision.content.origin,revision.content.subject,revision.content.body,revision.content.audience.id,revision.content.template_original_id):raise business_error("Campaign content differs from its literal request")
    return Original(request=request,revision=revision)
def original(db,institute,key):
    lock_institute(db,institute)
    row=db.scalar(select(CampaignOriginal).where(CampaignOriginal.institute_id==institute,CampaignOriginal.idempotency_key==key))
    return receipt(row) if row else None
def require(db,institute,identifier):
    lock_institute(db,institute)
    row=db.scalar(select(CampaignOriginal).where(CampaignOriginal.institute_id==institute,CampaignOriginal.id==identifier))
    if row is None:raise not_found("Campaign original not found")
    return receipt(row)
def head(db,institute,root):
    return db.scalar(select(CampaignHead).where(CampaignHead.institute_id==institute,CampaignHead.campaign_id==root).execution_options(populate_existing=True))
def current(db,institute,root):
    lock_institute(db,institute);pointer=head(db,institute,root)
    if pointer is None:return None
    result=require(db,institute,pointer.original_id)
    if result.revision.campaign_id!=root:raise business_error("Selected campaign scope is incoherent")
    return result
def source_content(db,institute,value,at):
    audience=audience_originals.campaign_audience(db,institute,value.audience_id,value.channel)
    if value.template_original_id is not None:
        original_template=templates.require(db,institute,value.template_original_id)
        if original_template.created_at>at:raise business_error("Template original is later than campaign capture")
        template=original_template.content
        if (template.channel,template.origin,template.subject,template.body)!=(value.channel,value.origin,value.subject,value.body):raise business_error("Template-bound campaign must retain the exact template content")
    return campaigns.CampaignContent(institute_id=institute,channel=value.channel,origin=value.origin,subject=value.subject,body=value.body,template_original_id=value.template_original_id,audience=audience)
def execute(db,institute,payload,actor):
    payload=Request.model_validate(payload.model_dump())
    if not isinstance(actor,str) or not actor.strip() or actor.strip()!=actor or len(actor)>160:raise business_error("Signed campaign actor required")
    old=original(db,institute,payload.idempotency_key)
    if old:
        if old.revision.actor_id!=actor or old.request!=payload:raise business_error("Campaign key retains actor and literal terms")
        return old
    root=payload.campaign_id or new_id("marketing_campaign");pointer=head(db,institute,root)
    if payload.expected_revision_id!=(pointer.original_id if pointer else None):raise business_error("Campaign changed; reread before action")
    now=utcnow();identifier=new_id("marketing_campaign_revision")
    try:
        if payload.action=="create":revision=campaigns.create(identifier,root,source_content(db,institute,payload.content,now),actor,payload.reason,now)
        else:
            prior=require(db,institute,pointer.original_id).revision
            content=source_content(db,institute,payload.content,now) if payload.content is not None else None
            if content is None:
                value=Content(channel=prior.content.channel,origin=prior.content.origin,subject=prior.content.subject,body=prior.content.body,audience_id=prior.content.audience.id,template_original_id=prior.content.template_original_id)
                if source_content(db,institute,value,now)!=prior.content:raise business_error("Retained campaign sources changed; cannot approve")
            revision=campaigns.transition(prior,payload.expected_revision_id,identifier,payload.action,actor,payload.reason,now,content)
    except ValueError as error:raise business_error(str(error)) from error
    row=CampaignOriginal(id=identifier,institute_id=institute,campaign_id=root,previous_id=revision.previous_id,audience_id=revision.content.audience.id,template_original_id=revision.content.template_original_id,actor_id=actor,reason=payload.reason,idempotency_key=payload.idempotency_key,created_at=now,request=payload.model_dump(mode="json"),revision=revision.model_dump(mode="json"))
    try:
        db.add(row);db.flush()
        if pointer:pointer.original_id=identifier
        else:db.add(CampaignHead(institute_id=institute,campaign_id=root,original_id=identifier))
        db.flush();result=receipt(row);db.commit();return result
    except Exception:
        db.rollback();raise

class AuditPage(Fact):
    institute_id: Identifier
    campaign_id: Identifier
    total: Count
    offset: Count
    limit: Count
    originals: tuple[Original,...]
def audit(db,institute,root,offset=0,limit=20):
    if type(offset) is not int or offset<0 or type(limit) is not int or not 1<=limit<=50:raise business_error("Bounded audit page required")
    if current(db,institute,root) is None:raise not_found("Campaign not found")
    scope=(CampaignOriginal.institute_id==institute,CampaignOriginal.campaign_id==root)
    total=db.scalar(select(func.count()).select_from(CampaignOriginal).where(*scope))
    rows=db.scalars(select(CampaignOriginal).where(*scope).order_by(CampaignOriginal.created_at,CampaignOriginal.id).offset(offset).limit(limit))
    return AuditPage(institute_id=institute,campaign_id=root,total=total,offset=offset,limit=limit,originals=tuple(receipt(row) for row in rows))
