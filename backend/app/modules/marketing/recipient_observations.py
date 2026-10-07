"""Bounded current declared eligibility; neither a retained send intent nor delivery."""
from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from app.modules.crm.metrics import Fact, Identifier, Count
from app.modules.crm.segments import RegisteredCustomerFact
from app.modules.marketing import contacts, contact_originals, campaign_originals
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import business_error, not_found
from app.shared.time import explicit_utc_instant, utcnow


class Item(Fact):
    customer: RegisteredCustomerFact
    original: contacts.Original | None
    reason: str
    eligible_by_current_declaration: bool = Field(strict=True)


class Page(Fact):
    institute_id: Identifier
    campaign: campaign_originals.Original
    expected_revision_id: Identifier
    captured_at: AwareDatetime
    total: Count
    offset: Count
    limit: int = Field(strict=True, ge=1, le=50)
    items: tuple[Item, ...]
    complete_campaign_evaluation: Literal[False] = False
    delivery_authorized: Literal[False] = False
    external_message_sent: Literal[False] = False

    @model_validator(mode="after")
    def coherent_page(self):
        campaign = campaign_originals.Original.model_validate(self.campaign.model_dump())
        revision = campaign.revision
        request = campaign.request
        expected_state = {"create": "DRAFT", "edit": "DRAFT", "review": "REVIEW", "approve": "APPROVE"}[request.action]
        if revision.state != expected_state or request.reason != revision.reason or request.expected_revision_id != revision.previous_id or request.campaign_id is not None and request.campaign_id != revision.campaign_id:
            raise ValueError("Retained campaign original terms must agree with its revision")
        if request.content is not None:
            content = request.content
            if (content.channel, content.origin, content.subject, content.body, content.audience_id, content.template_original_id) != (
                revision.content.channel, revision.content.origin, revision.content.subject, revision.content.body, revision.content.audience.id, revision.content.template_original_id):
                raise ValueError("Retained campaign original content must agree with its revision")
        members = revision.content.audience.customer_ids
        if revision.institute_id != self.institute_id or revision.id != self.expected_revision_id or self.total != len(members):
            raise ValueError("Observation must pin exact owned campaign revision and retained recipient count")
        expected = members[self.offset:self.offset + self.limit]
        if tuple(i.customer.customer_id for i in self.items) != expected:
            raise ValueError("Observation must retain exact bounded campaign recipient order")
        for item in self.items:
            observed = contacts.evaluate(item.customer, revision, item.original, self.captured_at)
            if item.reason != observed.reason or item.eligible_by_current_declaration != observed.eligible_by_current_declaration:
                raise ValueError("Observation must agree with its current declared eligibility sources")
        return self


def read(db, institute, campaign, expected_revision, offset=0, limit=20):
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 50:
        raise business_error("A bounded recipient observation page is required")
    lock_institute(db, institute)
    retained = campaign_originals.current(db, institute, campaign)
    if retained is None: raise not_found("Campaign not found")
    if retained.revision.id != expected_revision:
        raise business_error("Campaign changed; reread before recipient observation")
    clock = utcnow()
    members = retained.revision.content.audience.customer_ids
    items = []
    for identifier in members[offset:offset + limit]:
        registered = contact_originals.owned(db, institute, identifier)
        customer = RegisteredCustomerFact(institute_id=institute, customer_id=identifier, created_at=explicit_utc_instant(registered.created_at))
        original = contact_originals.current(db, institute, identifier)
        evaluated = contacts.evaluate(customer, retained.revision, original, clock)
        items.append(Item(customer=customer, original=original, reason=evaluated.reason,
                          eligible_by_current_declaration=evaluated.eligible_by_current_declaration))
    return Page(institute_id=institute, campaign=retained, expected_revision_id=expected_revision, captured_at=clock,
                total=len(members), offset=offset, limit=limit, items=tuple(items))
