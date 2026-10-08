"""Current sovereign matching plus explicit retained normalization assumptions."""
from typing import Annotated, Literal
from pydantic import AwareDatetime, StringConstraints
from app.modules.optimizer import domain, policy, originals
from app.modules.optimizer.models import PolicyOriginal
from app.modules.waitlist import sources as matching
from app.modules.services.models import Service
from app.modules.crm.metrics import microseconds
from app.modules.tickets.repository import lock_institute
from app.shared.time import utcnow
from app.shared.exceptions import business_error, not_found

Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class Request(domain.matching.Fact):
    policy_id: domain.Identifier
    policy_fingerprint: Digest
    root_id: domain.Identifier
    expected_event_id: domain.Identifier
    expected_event_fingerprint: Digest
    horizon_end: matching.Horizon
    matching_policy: matching.Policy


class Catalog(domain.matching.Fact):
    service_id: domain.Identifier
    price_member: str | None
    price_passage: str | None
    currency: Literal["not_recorded"] = "not_recorded"
    meaning: Literal["catalog_reference_not_customer_quote_or_profit"] = "catalog_reference_not_customer_quote_or_profit"


class OptionProof(domain.matching.Fact):
    option: domain.matching.Option
    containing_employee_window: domain.matching.Window
    factors: tuple[policy.Normalized, ...]


class Read(domain.matching.Fact):
    institute_id: domain.Identifier
    captured_at: AwareDatetime
    policy_original: originals.Envelope
    source: matching.Read
    catalog: Catalog | None
    proofs: tuple[OptionProof, ...]
    review: domain.Review | None
    action: Literal["human_review_then_revalidate_no_booking_or_contact"] = "human_review_then_revalidate_no_booking_or_contact"


UNKNOWN = {
    "revenue_score": "Catalog currency is not recorded; price cannot become monetary scoring evidence",
    "continuity_score": "Recorded care has no employee-linked continuity indicator",
    "client_preference_score": "Employee restrictions and availability are constraints, not a graded client preference",
    "employee_preference_score": "No explicit employee preference indicator is recorded",
    "overtime_penalty": "Declared working hours are unavailable; free capacity cannot prove overtime",
}


def derive(source: matching.Read, terms: policy.Terms):
    """Internal adapter only: never accepts HTTP observations or capacity payloads."""
    source = matching.Read.model_validate(source.model_dump())
    terms = policy.Terms.model_validate(terms.model_dump())
    if source.review is None:
        return ()
    review = source.review
    if domain.matching.match(review.demand, review.capture) != review or review.capture.captured_at != source.captured_at:
        raise ValueError("Complete sovereign source and shared capture required")
    rows = []
    for option in review.options:
        employee = next(e for e in review.capture.employees if e.employee_id == option.employee_id)
        window = next(w for w in employee.windows if w.start <= option.start and option.end <= w.end)
        factors = []
        for factor in domain.FACTORS:
            values = dict(factor=factor, basis=policy.BASES[factor], quantity=None, denominator=None,
                currency=None, price_mode=None, reference=None, observed_at=None, reason=UNKNOWN.get(factor, "Captured capacity evidence"))
            if factor == "utilization_score":
                values.update(quantity=str(microseconds(option.end-option.start)), denominator=str(microseconds(window.end-window.start)),
                    reference="proofs.containing_employee_window", observed_at=source.captured_at,
                    reason="Proposed elapsed duration over containing captured employee free window; not overall utilization")
            elif factor == "idle_gap_penalty":
                values.update(quantity=str(microseconds(option.start-source.captured_at)), reference="source.captured_at",
                    observed_at=source.captured_at, reason="Elapsed delay from current capture to option start; not measured employee idle time")
            elif factor == "resource_conflict_penalty":
                values.update(quantity="0", reference="source.review.capture.resources", observed_at=source.captured_at,
                    reason="Sovereign matching proves distinct resource fit in this capture only; revalidate before booking")
            factors.append(policy.normalize(next(r for r in terms.rules if r.factor == factor), policy.Source(**values), source.captured_at))
        rows.append(OptionProof(option=option, containing_employee_window=window, factors=tuple(factors)))
    return tuple(rows)


def read(db, institute, request: Request):
    try:
        request = Request.model_validate(request.model_dump())
        lock_institute(db, institute)
        now = utcnow()
        row = originals._row(db, institute, PolicyOriginal.id, request.policy_id)
        if row is None:
            raise not_found("Retained optimizer policy not found")
        envelope = originals.verify(row, institute, now)
        if envelope.fingerprint != request.policy_fingerprint:
            raise business_error("Selected policy fingerprint changed; reread before scoring")
        original = originals.Original.model_validate(envelope.original)
        source = matching.read(db, institute, request.root_id, request.expected_event_id,
            request.expected_event_fingerprint, request.horizon_end, request.matching_policy, _captured_at=now)
        proofs = derive(source, original.terms)
        catalog = None
        result = None
        if source.review is not None:
            service = db.get(Service, source.review.demand.service_id, populate_existing=True)
            catalog = Catalog(service_id=service.id, price_member=str(service.price_member) if service.price_member is not None else None,
                price_passage=str(service.price_passage) if service.price_passage is not None else None)
            evidence = tuple(domain.Evidence(option=p.option, factors=tuple(f.observation for f in p.factors), constraints=()) for p in proofs)
            result = domain.score(source.review, policy.scoring_policy(original.terms, institute, original.id, original.created_at, original.reason), evidence)
        return Read(institute_id=institute, captured_at=source.captured_at, policy_original=envelope,
            source=source, catalog=catalog, proofs=proofs, review=result)
    except (ValueError, TypeError, StopIteration) as error:
        raise business_error("Current optimizer evidence requires verification") from error
