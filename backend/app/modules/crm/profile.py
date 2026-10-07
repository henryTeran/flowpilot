"""A single locked snapshot of policy, customer and observed segment sources."""
from datetime import timedelta, timezone
from typing import Literal
from pydantic import AwareDatetime
from sqlalchemy import case, func, select
from app.modules.crm import billing, policies
from app.modules.crm.metrics import BillingWindow, Count, Fact, Identifier
from app.modules.crm.segments import ObservedSegment, RegisteredCustomerFact, classify
from app.modules.customers.repository import require_customer
from app.modules.tickets.models import QueueTicket
from app.modules.tickets.repository import lock_institute
from app.shared.time import explicit_utc_instant, utcnow


class SegmentProfile(Fact):
    institute_id: Identifier
    customer_id: Identifier
    captured_at: AwareDatetime
    customer: RegisteredCustomerFact
    policy_original: policies.PolicyRead | None
    undated_paid_tickets: Count
    future_paid_tickets: Count
    segment: ObservedSegment | None
    unavailable_reason: Literal["policy_absent", "future_policy", "future_registration",
        "future_closings", "unrepresentable_horizon"] | None
    complete_customer_history: Literal[False] = False


def read(db, institute, customer):
    lock_institute(db, institute)
    registered = require_customer(db, institute, customer)
    registration = RegisteredCustomerFact(institute_id=institute, customer_id=customer,
        created_at=explicit_utc_instant(registered.created_at))
    head = policies.read_head(db, institute)
    original = policies.require(db, institute, head.policy_id) if head else None
    now = utcnow()
    undated, future = db.execute(select(
        func.sum(case((QueueTicket.paid_at.is_(None), 1), else_=0)),
        func.sum(case((QueueTicket.paid_at > now.astimezone(timezone.utc), 1), else_=0)))
        .where(QueueTicket.institute_id == institute, QueueTicket.customer_id == customer,
            QueueTicket.status == "paid")).one()
    undated, future = undated or 0, future or 0
    segment = None
    reason = None
    if original is None:
        reason = "policy_absent"
    elif original.created_at > now:
        reason = "future_policy"
    elif registration.created_at > now:
        reason = "future_registration"
    elif future:
        reason = "future_closings"
    else:
        try:
            start = now-timedelta(microseconds=original.policy.observation_us)
        except OverflowError:
            reason = "unrepresentable_horizon"
        else:
            window = BillingWindow(institute_id=institute, customer_id=customer,
                start=start, end=now, captured_at=now)
            metric = billing.capture(db, window)
            segment = classify(original.policy, registration, metric, undated)
    return SegmentProfile(institute_id=institute, customer_id=customer, captured_at=now,
        customer=registration, policy_original=original, undated_paid_tickets=undated,
        future_paid_tickets=future, segment=segment, unavailable_reason=reason)
