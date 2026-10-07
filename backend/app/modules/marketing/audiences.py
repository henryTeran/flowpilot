"""Bounded owned segmentation observations; not a sendable contact list."""
from typing import Literal
from pydantic import AwareDatetime, Field, model_validator
from sqlalchemy import select
from app.modules.crm.metrics import Fact, Identifier
from app.modules.crm import profile, lifecycle_originals
from app.modules.crm.segments import classify
from app.modules.customers.models import Customer
from app.modules.tickets.repository import lock_institute
from app.shared.time import utcnow, explicit_utc_instant

State=Literal["NEW","ACTIVE","LOYAL","VIP","AT_RISK","DORMANT"]
class Selection(Fact):
    segments: tuple[State,...]
    channel: Literal["sms","email","push"]
    after: Identifier | None

    @model_validator(mode="after")
    def explicit_segments(self):
        if not self.segments or len(set(self.segments))!=len(self.segments):
            raise ValueError("Explicit unique CRM segments required")
        if self.after is not None and (not self.after.strip() or self.after.strip()!=self.after):
            raise ValueError("Exact customer cursor required")
        return self

class Item(Fact):
    customer_id: Identifier
    profile: profile.SegmentProfile
    declaration: lifecycle_originals.Original | None
    selected_segment: bool = Field(strict=True)
    marketing_permission: Literal["granted","refused","unknown","unsupported_channel","future_declaration"]
    eligible_by_recorded_permission: bool = Field(strict=True)
    delivery_authorized: Literal[False] = False

class Page(Fact):
    institute_id: Identifier
    captured_at: AwareDatetime
    selection: Selection
    next_after: Identifier | None
    items: tuple[Item,...]
    complete_institute_audience: Literal[False] = False
    delivery_authorized: Literal[False] = False

    @model_validator(mode="after")
    def coherent_snapshot(self):
        if len(self.items)>50:
            raise ValueError("Audience page exceeds the bounded scan")
        previous=self.selection.after or ""
        for item in self.items:
            observed=profile.SegmentProfile.model_validate(item.profile.model_dump())
            if (not item.customer_id.strip() or item.customer_id.strip()!=item.customer_id or item.customer_id<=previous
                or observed.institute_id!=self.institute_id or observed.customer_id!=item.customer_id
                or observed.captured_at!=self.captured_at or observed.customer.institute_id!=self.institute_id
                or observed.customer.customer_id!=item.customer_id):
                raise ValueError("Unique ordered own customer observations at one capture required")
            previous=item.customer_id
            if observed.policy_original is not None and (observed.policy_original.institute_id!=self.institute_id or observed.policy_original.policy.institute_id!=self.institute_id):
                raise ValueError("Segment policy scope must agree")
            if observed.segment is not None:
                if observed.policy_original is None or observed.policy_original.created_at>self.captured_at or observed.customer.created_at>self.captured_at or observed.unavailable_reason is not None or observed.future_paid_tickets:
                    raise ValueError("Unavailable segment sources cannot classify an audience")
                metric=observed.segment.billing
                if metric.window.captured_at!=self.captured_at or metric.window.customer_id!=item.customer_id or metric.window.institute_id!=self.institute_id or observed.segment!=classify(observed.policy_original.policy,observed.customer,metric,observed.undated_paid_tickets):
                    raise ValueError("Audience segment must match its retained source calculation")
            selected=observed.segment is not None and observed.segment.state in self.selection.segments
            declaration=item.declaration
            if declaration is not None:
                declaration=lifecycle_originals.Original.model_validate(declaration.model_dump())
                if (declaration.institute_id,declaration.customer_id)!=(self.institute_id,item.customer_id) or (declaration.declaration.institute_id,declaration.declaration.customer_id)!=(self.institute_id,item.customer_id):
                    raise ValueError("Permission original must belong to the observed customer")
            permission=recorded_permission(self.selection.channel,declaration,self.captured_at)
            if item.selected_segment!=selected or item.marketing_permission!=permission or item.eligible_by_recorded_permission!=(selected and permission=="granted"):
                raise ValueError("Audience eligibility must match segment and exact marketing permission")
        if self.next_after is not None and (len(self.items)!=50 or self.next_after!=previous):
            raise ValueError("Next cursor must pin the full page's final observed customer")
        return self

def recorded_permission(channel,declaration,at):
    if channel=="push":return "unsupported_channel"
    if declaration is None:return "unknown"
    if declaration.created_at>at:return "future_declaration"
    return next(p.permission for p in declaration.declaration.communications if p.channel==channel and p.purpose=="marketing")

def read(db,institute,selection,*,_captured_at=None):
    selection=Selection.model_validate(selection.model_dump())
    lock_institute(db,institute)
    now=explicit_utc_instant(_captured_at) if _captured_at is not None else utcnow()
    query=select(Customer.id).where(Customer.institute_id==institute)
    if selection.after is not None:query=query.where(Customer.id>selection.after)
    ids=list(db.scalars(query.order_by(Customer.id).limit(51)))
    items=[]
    for customer in ids[:50]:
        observed=profile.read(db,institute,customer,_captured_at=now)
        declaration=lifecycle_originals.current(db,institute,customer)
        permission=recorded_permission(selection.channel,declaration,now)
        selected=observed.segment is not None and observed.segment.state in selection.segments
        items.append(Item(customer_id=customer,profile=observed,declaration=declaration,selected_segment=selected,marketing_permission=permission,eligible_by_recorded_permission=selected and permission=="granted"))
    return Page(institute_id=institute,captured_at=now,selection=selection,next_after=ids[49] if len(ids)>50 else None,items=tuple(items))
