"""Append-only owned plain-text templates; no message rendering or transport."""
from typing import Annotated,Literal
from pydantic import AwareDatetime,StringConstraints,model_validator
from sqlalchemy import select
from app.modules.crm.metrics import Fact,Identifier
from app.modules.crm.policies import Reason,Key
from app.modules.marketing.models import TemplateOriginal,TemplateHead
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import business_error,not_found
from app.shared.ids import new_id
from app.shared.time import utcnow,explicit_utc_instant

class Content(Fact):
    name: Annotated[str,StringConstraints(min_length=1,max_length=160)]
    channel: Literal["email","sms","push"]
    origin: Literal["human","ai"]
    subject: Annotated[str,StringConstraints(min_length=1,max_length=240)] | None
    body: Annotated[str,StringConstraints(min_length=1,max_length=10000)]
    @model_validator(mode="after")
    def explicit_content(self):
        if not self.name.strip() or self.name.strip()!=self.name or not self.body.strip() or self.subject is not None and not self.subject.strip() or (self.channel=="email")!=(self.subject is not None):
            raise ValueError("Explicit template name/body and email-only subject required")
        return self

class Request(Fact):
    template_id: Identifier | None
    previous_id: Identifier | None
    content: Content
    reason: Reason
    idempotency_key: Key
    @model_validator(mode="after")
    def explicit_target(self):
        if (self.template_id is None)!=(self.previous_id is None):raise ValueError("New template has no target; correction pins root and original")
        return self

class Original(Fact):
    id: Identifier
    institute_id: Identifier
    template_id: Identifier
    previous_id: Identifier | None
    actor_id: Annotated[str,StringConstraints(min_length=1,max_length=160)]
    created_at: AwareDatetime
    request: Request
    content: Content

def receipt(row):
    result=Original(id=row.id,institute_id=row.institute_id,template_id=row.template_id,previous_id=row.previous_id,actor_id=row.actor_id,created_at=explicit_utc_instant(row.created_at),request=row.request,content=row.content)
    if result.id==result.previous_id or result.request.previous_id!=result.previous_id or result.request.template_id is not None and result.request.template_id!=result.template_id or result.request.content!=result.content or result.request.reason!=row.reason or result.request.idempotency_key!=row.idempotency_key:
        raise business_error("Stored template original scope or terms are incoherent")
    return result

def original(db,institute,key):
    lock_institute(db,institute)
    row=db.scalar(select(TemplateOriginal).where(TemplateOriginal.institute_id==institute,TemplateOriginal.idempotency_key==key))
    return receipt(row) if row else None

def require(db,institute,identifier):
    lock_institute(db,institute)
    row=db.scalar(select(TemplateOriginal).where(TemplateOriginal.institute_id==institute,TemplateOriginal.id==identifier))
    if row is None:raise not_found("Template original not found")
    return receipt(row)

def head(db,institute,template):
    return db.scalar(select(TemplateHead).where(TemplateHead.institute_id==institute,TemplateHead.template_id==template).execution_options(populate_existing=True))

def current(db,institute,template):
    lock_institute(db,institute);pointer=head(db,institute,template)
    if pointer is None:return None
    result=require(db,institute,pointer.original_id)
    if result.template_id!=template:raise business_error("Selected template scope is incoherent")
    return result

def create(db,institute,payload,actor):
    payload=Request.model_validate(payload.model_dump())
    if not isinstance(actor,str) or not actor.strip() or actor.strip()!=actor or len(actor)>160:raise business_error("Signed template actor required")
    old=original(db,institute,payload.idempotency_key)
    if old:
        if old.actor_id!=actor or old.request!=payload:raise business_error("Template key retains original terms and actor")
        return old
    root=payload.template_id or new_id("marketing_template")
    pointer=head(db,institute,root)
    if payload.previous_id!=(pointer.original_id if pointer else None):raise business_error("Template changed; reread before correction")
    now=utcnow()
    if pointer and now<require(db,institute,pointer.original_id).created_at:raise business_error("Template clock precedes its predecessor")
    row=TemplateOriginal(id=new_id("marketing_template_revision"),institute_id=institute,template_id=root,previous_id=payload.previous_id,actor_id=actor,reason=payload.reason,idempotency_key=payload.idempotency_key,created_at=now,request=payload.model_dump(mode="json"),content=payload.content.model_dump(mode="json"))
    try:
        db.add(row);db.flush()
        if pointer:pointer.original_id=row.id
        else:db.add(TemplateHead(institute_id=institute,template_id=root,original_id=row.id))
        db.flush();result=receipt(row);db.commit();return result
    except Exception:
        db.rollback();raise
