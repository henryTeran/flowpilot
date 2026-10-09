"""Minimal projection of existing institute-wide rebooking opportunities."""
from typing import Literal
from pydantic import AwareDatetime, model_validator
from app.modules.base.read_capabilities import Digest
from app.modules.crm.metrics import Fact, Count, Identifier
from app.modules.crm.event_candidates import EventCandidate
from app.modules.revenue import rebooking
from app.modules.waitlist.originals import fingerprint


class Returns(Fact):
    institute_id: Identifier
    captured_at: AwareDatetime
    source_digest: Digest
    source: Literal["observed_care_declared_rebooking_rule"] = "observed_care_declared_rebooking_rule"
    total_candidates: Count
    examined_customers: Count
    already_booked_customers: Count
    scheduled_customers: Count
    disabled_customers: Count
    no_candidate_customers: Count
    diagnostics: dict[str, Count]
    candidates: tuple[EventCandidate, ...]
    page_limit: Literal[20] = 20
    estimated_value: None = None
    delivery_authorized: Literal[False] = False
    action_executed: Literal[False] = False
    complete_customer_history: Literal[False] = False

    @model_validator(mode="after")
    def coherent_candidates(self):
        if len(self.candidates) != min(self.total_candidates, self.page_limit):
            raise ValueError("First-page candidates must match total and page bound")
        if len({row.customer_id for row in self.candidates}) != len(self.candidates):
            raise ValueError("At most one rebooking opportunity per customer")
        for row in self.candidates:
            if (row.institute_id != self.institute_id or row.captured_at != self.captured_at
                or row.state != "due" or row.rule.trigger != "rebooking"
                or row.source.source_kind != "care_episode" or row.source.institute_id != self.institute_id
                or row.source.customer_id != row.customer_id):
                raise ValueError("Own due rebooking sources and capture required")
        return self


def read_returns(db, institute):
    source = rebooking.read(db, institute)
    return Returns(institute_id=institute, captured_at=source.captured_at,
        source_digest=fingerprint(source.model_dump(mode="json")), total_candidates=source.page.total,
        candidates=tuple(row.candidate for row in source.opportunities), **source.model_dump(include={
            "examined_customers", "already_booked_customers", "scheduled_customers", "disabled_customers",
            "no_candidate_customers", "diagnostics"}))
