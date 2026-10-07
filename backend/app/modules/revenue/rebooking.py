"""Observed CRM rebooking candidates, suppressed by an already active return."""
from typing import Literal
from pydantic import AwareDatetime, field_validator
from sqlalchemy import select, or_
from app.modules.crm import event_sources, automation_originals, lifecycle_originals
from app.modules.crm.event_candidates import EventCandidate
from app.modules.crm.metrics import Fact, Identifier, Count
from app.modules.crm.segments import RegisteredCustomerFact
from app.modules.customers.models import Customer
from app.modules.appointments.models import Appointment
from app.modules.employees.models import Employee
from app.modules.services.models import Service
from app.modules.tickets.repository import lock_institute
from app.modules.workforce.schemas import MatrixPage
from app.shared.exceptions import business_error
from app.shared.time import utcnow, explicit_utc_instant


class Evidence(Fact):
    institute_id: Identifier
    customer_id: Identifier
    captured_at: AwareDatetime
    customer: RegisteredCustomerFact
    policy_original: automation_originals.PolicyRead
    lifecycle_original: lifecycle_originals.Original | None
    lifecycle_unavailable_reason: str | None
    diagnostics: dict[str, Count]


class Opportunity(Fact):
    type: Literal["review_due_rebooking"] = "review_due_rebooking"
    evidence: Evidence
    candidate: EventCandidate
    estimated_value: None = None
    confidence: Literal["observed_care_and_declared_rule_only"] = "observed_care_and_declared_rule_only"
    recommended_action: Literal["review_return_need_contact_permission_and_feasible_slot"] = "review_return_need_contact_permission_and_feasible_slot"
    action_executed: Literal[False] = False

    @field_validator("action_executed", mode="before")
    @classmethod
    def no_action(cls, value):
        if value is not False:
            raise ValueError("An opportunity read cannot execute a follow-up")
        return value


class Rebooking(Fact):
    institute_id: Identifier
    captured_at: AwareDatetime
    basis: Literal["latest_observed_care_and_current_declared_rebooking_rule"] = "latest_observed_care_and_current_declared_rebooking_rule"
    page: MatrixPage
    opportunities: tuple[Opportunity, ...]
    examined_customers: Count
    already_booked_customers: Count
    scheduled_customers: Count
    disabled_customers: Count
    no_candidate_customers: Count
    diagnostics: dict[str, Count]
    complete_customer_history: Literal[False] = False
    delivery_authorized: Literal[False] = False
    external_message_sent: Literal[False] = False

    @field_validator("complete_customer_history", "delivery_authorized", "external_message_sent", mode="before")
    @classmethod
    def no_claim(cls, value):
        if value is not False:
            raise ValueError("A candidate is not a complete history or contact authorization")
        return value


def read(db, institute, offset=0, limit=20):
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 50:
        raise business_error("Invalid rebooking page bounds")
    lock_institute(db, institute)
    now = utcnow()
    total = examined = booked = scheduled = disabled = absent = 0
    rows, diagnostics = [], {}
    try:
        for customer in db.scalars(select(Customer.id).where(Customer.institute_id == institute).order_by(Customer.id)
            .execution_options(yield_per=100)):
            examined += 1
            source = event_sources.read(db, institute, customer, _captured_at=now)
            if source.institute_id != institute or source.customer_id != customer or source.captured_at != now \
                    or source.lifecycle.captured_at != now:
                raise ValueError("Rebooking evidence must share institute, customer and capture")
            # Do not turn unrelated absent birthdays/packages into missing-care
            # conclusions. Existing CRM capture controls all candidate derivation.
            for key, count in source.diagnostics.items():
                if key in {"policy_absent", "future_policy", "future_registration", "invalid_event_timing"} or key.startswith("care_"):
                    diagnostics[key] = diagnostics.get(key, 0)+count
            candidates = [candidate for candidate in source.candidates if candidate.rule.trigger == "rebooking"]
            if len(candidates) > 1:
                raise ValueError("Latest-care rebooking must have one candidate per customer")
            if not candidates:
                absent += 1
                continue
            candidate = candidates[0]
            if candidate.state == "disabled":
                disabled += 1
                continue
            if candidate.state == "scheduled":
                scheduled += 1
                continue
            if candidate.state != "due":
                raise ValueError("Unsupported rebooking candidate state")
            active = 0
            for appointment, employee, service in db.execute(select(Appointment, Employee.id, Service.id)
                .outerjoin(Employee, (Employee.id == Appointment.employee_id) & (Employee.institute_id == institute))
                .outerjoin(Service, Service.id == Appointment.service_id).where(Appointment.institute_id == institute,
                    Appointment.customer_id == customer, Appointment.status.in_(["scheduled", "confirmed", "arrived", "in_progress"]),
                    or_(Appointment.end_time > now, Appointment.start_time >= now))):
                first, last = explicit_utc_instant(appointment.start_time), explicit_utc_instant(appointment.end_time)
                if employee is None or service is None or last <= first:
                    raise ValueError("An active return booking requires owned valid slot evidence")
                active += 1
            if active:
                booked += 1
                continue
            if offset <= total < offset+limit:
                # Return the selected rule/source and original permission terms,
                # not every historical anchor or unrelated package/birthday.
                evidence = Evidence(institute_id=institute, customer_id=customer, captured_at=now, customer=source.customer,
                    policy_original=source.policy_original, lifecycle_original=source.lifecycle.original,
                    lifecycle_unavailable_reason=source.lifecycle.unavailable_reason,
                    diagnostics={key: value for key, value in source.diagnostics.items()
                        if key in {"policy_absent", "future_policy", "future_registration", "invalid_event_timing"} or key.startswith("care_")})
                rows.append(Opportunity(evidence=evidence, candidate=candidate))
            total += 1
    except ValueError as error:
        raise business_error("Rebooking sources require verification") from error
    return Rebooking(institute_id=institute, captured_at=now, page=MatrixPage(offset=offset, limit=limit, total=total),
        opportunities=tuple(rows), examined_customers=examined, already_booked_customers=booked,
        scheduled_customers=scheduled, disabled_customers=disabled, no_candidate_customers=absent, diagnostics=diagnostics)
