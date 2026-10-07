"""Bounded owned segmentation observations; not a sendable contact list."""
from typing import Literal
from pydantic import AwareDatetime, model_validator
from sqlalchemy import select
from app.modules.crm.metrics import Fact, Identifier
from app.modules.crm import profile, lifecycle_originals
from app.modules.customers.models import Customer
from app.modules.tickets.repository import lock_institute
from app.shared.time import utcnow

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
    selected_segment: bool
    marketing_permission: Literal["granted","refused","unknown","unsupported_channel","future_declaration"]
    eligible_by_recorded_permission: bool
    delivery_authorized: Literal[False] = False

class Page(Fact):
    institute_id: Identifier
    captured_at: AwareDatetime
    selection: Selection
    next_after: Identifier | None
    items: tuple[Item,...]
    complete_institute_audience: Literal[False] = False
    delivery_authorized: Literal[False] = False

def read(db,institute,selection):
    selection=Selection.model_validate(selection.model_dump())
    lock_institute(db,institute)
    now=utcnow()
    query=select(Customer.id).where(Customer.institute_id==institute)
    if selection.after is not None:query=query.where(Customer.id>selection.after)
    ids=list(db.scalars(query.order_by(Customer.id).limit(51)))
    items=[]
    for customer in ids[:50]:
        observed=profile.read(db,institute,customer,_captured_at=now)
        declaration=lifecycle_originals.current(db,institute,customer)
        permission="unknown"
        if selection.channel=="push":permission="unsupported_channel"
        elif declaration is not None:
            if declaration.created_at>now:permission="future_declaration"
            else:permission=next(p.permission for p in declaration.declaration.communications if p.channel==selection.channel and p.purpose=="marketing")
        selected=observed.segment is not None and observed.segment.state in selection.segments
        items.append(Item(customer_id=customer,profile=observed,declaration=declaration,selected_segment=selected,marketing_permission=permission,eligible_by_recorded_permission=selected and permission=="granted"))
    return Page(institute_id=institute,captured_at=now,selection=selection,next_after=ids[49] if len(ids)>50 else None,items=tuple(items))
