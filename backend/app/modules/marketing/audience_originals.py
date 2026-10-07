"""Atomic whole registered-cohort captures; historical permissions never authorize send."""
from typing import Annotated, Literal
from pydantic import AwareDatetime, Field, StringConstraints, model_validator
from sqlalchemy import select
from app.modules.crm.metrics import Fact, Identifier, Count
from app.modules.crm.policies import Reason, Key
from app.modules.marketing import audiences
from app.modules.marketing.models import AudienceOriginal, AudiencePage
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import business_error, not_found
from app.shared.ids import new_id
from app.shared.time import utcnow, explicit_utc_instant

class Request(Fact):
    segments: tuple[audiences.State,...]
    channel: Literal["sms","email","push"]
    reason: Reason
    idempotency_key: Key
    @model_validator(mode="after")
    def explicit_selection(self):
        audiences.Selection(segments=self.segments,channel=self.channel,after=None)
        return self

class Summary(Fact):
    page_count: Annotated[int,Field(strict=True,ge=1)]
    customer_count: Count
    selected_count: Count
    eligible_count: Count
    @model_validator(mode="after")
    def counts(self):
        if self.page_count!=max(1,(self.customer_count+49)//50) or not self.eligible_count<=self.selected_count<=self.customer_count:
            raise ValueError("Audience summary counts must agree")
        return self

class ContactRequest(Request):
    permission_basis: Literal["marketing_contact"]

class Original(Fact):
    id: Identifier
    institute_id: Identifier
    actor_id: Annotated[str,StringConstraints(min_length=1,max_length=160)]
    captured_at: AwareDatetime
    request: Request | ContactRequest
    summary: Summary
    complete_registered_cohort: Literal[True] = True
    delivery_authorized: Literal[False] = False

class RetainedPage(Fact):
    capture_id: Identifier
    page_index: Count
    observation: audiences.Page | audiences.ContactPage

def observation(value):
    model = audiences.ContactPage if value.get("selection", {}).get("permission_basis") == "marketing_contact" else audiences.Page
    return model.model_validate(value)

def basis(value):
    return getattr(value, "permission_basis", "legacy_lifecycle")

def receipt(row):
    result=Original(id=row.id,institute_id=row.institute_id,actor_id=row.actor_id,captured_at=explicit_utc_instant(row.captured_at),request=row.request,summary=row.summary)
    if result.request.reason!=row.reason or result.request.idempotency_key!=row.idempotency_key:
        raise business_error("Retained audience request terms are incoherent")
    return result

def original(db,institute,key):
    lock_institute(db,institute)
    row=db.scalar(select(AudienceOriginal).where(AudienceOriginal.institute_id==institute,AudienceOriginal.idempotency_key==key))
    return receipt(row) if row else None

def require(db,institute,identifier):
    lock_institute(db,institute)
    row=db.scalar(select(AudienceOriginal).where(AudienceOriginal.institute_id==institute,AudienceOriginal.id==identifier))
    if row is None:raise not_found("Audience original not found")
    return receipt(row)

def page(db,institute,identifier,index):
    cap=require(db,institute,identifier)
    if type(index) is not int or index<0 or index>=cap.summary.page_count:raise not_found("Audience page not found")
    row=db.get(AudiencePage,(institute,identifier,index))
    if row is None:raise business_error("Retained audience page is missing")
    observed=observation(row.observation)
    if basis(observed.selection)!=basis(cap.request):raise business_error("Retained audience permission basis is incoherent")
    if observed.institute_id!=institute or observed.captured_at!=cap.captured_at or observed.selection.segments!=cap.request.segments or observed.selection.channel!=cap.request.channel:
        raise business_error("Retained audience page scope or terms are incoherent")
    previous=None
    if index:
        prior=db.get(AudiencePage,(institute,identifier,index-1))
        if prior is None:raise business_error("Retained audience predecessor page is missing")
        prior_page=observation(prior.observation)
        if basis(prior_page.selection)!=basis(cap.request):raise business_error("Retained audience predecessor permission basis is incoherent")
        if prior_page.institute_id!=institute or prior_page.captured_at!=cap.captured_at or prior_page.selection.segments!=cap.request.segments or prior_page.selection.channel!=cap.request.channel:raise business_error("Retained audience predecessor scope is incoherent")
        previous=prior_page.next_after
        if previous is None:raise business_error("Retained audience predecessor already ended")
    if observed.selection.after!=previous or (index==cap.summary.page_count-1)!=(observed.next_after is None):
        raise business_error("Retained audience page chain is incoherent")
    return RetainedPage(capture_id=identifier,page_index=index,observation=observed)

def create(db,institute,payload,actor):
    model=ContactRequest if basis(payload)=="marketing_contact" else Request
    payload=model.model_validate(payload.model_dump())
    if not isinstance(actor,str) or not actor.strip() or actor.strip()!=actor or len(actor)>160:raise business_error("Signed audience actor required")
    old=original(db,institute,payload.idempotency_key)
    if old:
        if old.actor_id!=actor or old.request!=payload:raise business_error("Audience key retains original terms and actor")
        return old
    now=utcnow()
    row=AudienceOriginal(id=new_id("marketing_audience"),institute_id=institute,actor_id=actor,reason=payload.reason,idempotency_key=payload.idempotency_key,captured_at=now,request=payload.model_dump(mode="json"),summary={})
    try:
        db.add(row);db.flush()
        after=None;index=0;customers=selected=eligible=0
        while True:
            if isinstance(payload,ContactRequest):
                observed=audiences.read_contacts(db,institute,audiences.ContactSelection(segments=payload.segments,channel=payload.channel,after=after,permission_basis=payload.permission_basis),_captured_at=now)
            else:
                observed=audiences.read(db,institute,audiences.Selection(segments=payload.segments,channel=payload.channel,after=after),_captured_at=now)
            db.add(AudiencePage(institute_id=institute,capture_id=row.id,page_index=index,observation=observed.model_dump(mode="json")));db.flush()
            customers+=len(observed.items);selected+=sum(i.selected_segment for i in observed.items);eligible+=sum(i.eligible_by_recorded_permission for i in observed.items);index+=1
            if observed.next_after is None:break
            after=observed.next_after
        row.summary=Summary(page_count=index,customer_count=customers,selected_count=selected,eligible_count=eligible).model_dump(mode="json")
        db.flush();result=receipt(row);db.commit();return result
    except Exception:
        db.rollback();raise

def campaign_audience(db,institute,identifier,channel):
    """Build historical campaign recipient terms only from verified retained pages."""
    from sqlalchemy import func
    from app.modules.marketing.campaigns import AudienceFact
    cap=require(db,institute,identifier)
    if cap.request.channel!=channel:
        raise business_error("Campaign channel must match the retained audience")
    count=db.scalar(select(func.count()).select_from(AudiencePage).where(AudiencePage.institute_id==institute,AudiencePage.capture_id==identifier))
    if count!=cap.summary.page_count:
        raise business_error("Audience retained page count is incoherent")
    customers=selected=eligible=0;recipients=[]
    for index in range(cap.summary.page_count):
        observed=page(db,institute,identifier,index).observation
        customers+=len(observed.items);selected+=sum(i.selected_segment for i in observed.items)
        for item in observed.items:
            if item.eligible_by_recorded_permission:
                recipients.append(item.customer_id);eligible+=1
    if (customers,selected,eligible)!=(cap.summary.customer_count,cap.summary.selected_count,cap.summary.eligible_count):
        raise business_error("Audience manifest does not match its retained pages")
    if not recipients:
        raise business_error("No customers qualify under the retained marketing permission")
    return AudienceFact(id=cap.id,institute_id=institute,captured_at=cap.captured_at,customer_ids=tuple(recipients))
