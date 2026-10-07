"""Locked registered-customer lifecycle capture; no durable event or delivery yet."""
from typing import Literal
from pydantic import AwareDatetime, ValidationError
from sqlalchemy import select
from app.modules.crm import automation_originals, lifecycle_originals, return_sources
from app.modules.crm.event_candidates import EventAnchor, EventCandidate, candidates
from app.modules.crm.metrics import BillingWindow, Count, Fact, Identifier
from app.modules.crm.segments import RegisteredCustomerFact
from app.modules.commerce.models import CustomerPackage
from app.modules.memberships.models import CustomerMembership
from app.modules.customers.repository import require_customer
from app.modules.tickets.repository import lock_institute
from app.shared.time import explicit_utc_instant, utcnow


class EventSourceRead(Fact):
    institute_id: Identifier
    customer_id: Identifier
    captured_at: AwareDatetime
    customer: RegisteredCustomerFact
    policy_original: automation_originals.PolicyRead | None
    lifecycle: lifecycle_originals.LifecycleRead
    anchors: tuple[EventAnchor, ...]
    candidates: tuple[EventCandidate, ...]
    diagnostics: dict[str, Count]
    complete_customer_history: Literal[False] = False
    external_message_sent: Literal[False] = False
    delivery_authorized: Literal[False] = False


def read(db, institute, customer):
    lock_institute(db, institute)
    row = require_customer(db, institute, customer)
    registered = RegisteredCustomerFact(institute_id=institute,customer_id=customer,created_at=explicit_utc_instant(row.created_at))
    pointer = automation_originals.read_head(db,institute)
    policy = automation_originals.require(db,institute,pointer.policy_id) if pointer else None
    now = utcnow()
    life = lifecycle_originals.read(db,institute,customer,_captured_at=now)
    diagnostics = {key: 0 for key in ("policy_absent", "future_policy", "future_registration", "birthday_unavailable",
        "care_unavailable", "care_unlinked_ticket", "care_invalid_owner_or_service", "care_invalid_actual_times",
        "invalid_event_timing", "package_absent", "membership_absent", "invalid_package", "invalid_membership")}
    diagnostics["policy_absent"] = int(policy is None)
    diagnostics["future_policy"] = int(policy is not None and policy.created_at > now)
    diagnostics["future_registration"] = int(registered.created_at > now)
    diagnostics["birthday_unavailable"] = int(life.birthday is None or life.birthday.occurrence_start is None)
    anchors = []
    if life.birthday and life.birthday.occurrence_start:
        anchors.append(EventAnchor(institute_id=institute,customer_id=customer,source_id=str(life.birthday.anniversary_on),
            source_kind="birthday",occurred_at=life.birthday.occurrence_start,expires_at=life.birthday.occurrence_end,remaining=None))
    if registered.created_at < now:
        result, care_diagnostics = return_sources.capture(db,BillingWindow(institute_id=institute,customer_id=customer,
            start=registered.created_at,end=now,captured_at=now))
        diagnostics["care_unavailable"] = int(result.episode_count == 0)
        for key,value in care_diagnostics.items(): diagnostics["care_"+key] = value
        # An invalid completed source can alter last completion; do not infer recency from the remaining subset.
        if not any(care_diagnostics.values()):
            anchors.extend(EventAnchor(institute_id=institute,customer_id=customer,source_id=e.ticket_id,
                source_kind="care_episode",occurred_at=e.completed_at,expires_at=None,remaining=None) for e in result.episodes)
    else:
        diagnostics["care_unavailable"] = 1
    for model,kind,error_key in ((CustomerPackage,"package","invalid_package"),(CustomerMembership,"membership","invalid_membership")):
        rows = db.scalars(select(model).where(model.institute_id==institute,model.customer_id==customer)
            .execution_options(yield_per=100,populate_existing=True))
        count = 0
        for source in rows:
            count += 1
            try:
                issued = explicit_utc_instant(source.issued_at)
                start = issued if kind=="package" else explicit_utc_instant(source.active_from)
                end = explicit_utc_instant(source.expires_at if kind=="package" else source.active_until)
                if not registered.created_at <= issued <= start <= now:
                    raise ValueError("Source chronology cannot establish an observed owned term")
                remaining = source.sessions-source.consumed if kind=="package" else None
                if kind=="package" and (source.sessions <= 0 or source.consumed < 0):
                    raise ValueError("Invalid package source balance")
                anchors.append(EventAnchor(institute_id=institute,customer_id=customer,source_id=source.id,
                    source_kind=kind,occurred_at=start,expires_at=end,remaining=remaining))
            except (ValidationError,ValueError,TypeError,OverflowError):
                diagnostics[error_key] += 1
        diagnostics["package_absent" if kind=="package" else "membership_absent"] = int(count == 0)
    eligible = policy is not None and not diagnostics["future_policy"] and not diagnostics["future_registration"]
    derived = ()
    if eligible:
        try: derived = candidates(policy.policy,policy.id,registered,now,tuple(anchors))
        except (ValueError,OverflowError): diagnostics["invalid_event_timing"] = 1
    return EventSourceRead(institute_id=institute,customer_id=customer,captured_at=now,customer=registered,
        policy_original=policy,lifecycle=life,anchors=tuple(anchors),candidates=derived,diagnostics=diagnostics)
