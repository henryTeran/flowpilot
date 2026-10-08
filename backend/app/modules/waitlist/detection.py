"""Whole-active-waitlist conditional detection with independently paged reviews."""
from datetime import datetime, timezone
from typing import Literal
from pydantic import AwareDatetime
from sqlalchemy import select
from app.modules.waitlist import domain, lifecycle, sources
from app.modules.waitlist.models import LifecycleOriginal
from app.modules.crm.metrics import Identifier, Count
from app.modules.tickets.repository import lock_institute
from app.shared.time import utcnow
from app.shared.exceptions import business_error


class Detection(domain.Fact):
    institute_id: Identifier
    captured_at: AwareDatetime
    horizon_end: AwareDatetime
    policy: sources.Policy
    offset: Count
    limit: Count
    examined_roots: Count
    active: Count
    cancelled: Count
    with_options: Count
    without_options: Count
    unavailable_reasons: dict[str, Count]
    reviews: tuple[sources.Read, ...]
    basis: Literal["whole_active_cohort_verified_before_paging"] = "whole_active_cohort_verified_before_paging"
    allocation: Literal["independent_alternatives_not_jointly_reserved"] = "independent_alternatives_not_jointly_reserved"
    action: Literal["no_booking_or_contact"] = "no_booking_or_contact"


def read(db, institute, horizon_end, policy: sources.Policy, offset=0, limit=20):
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 50:
        raise business_error("Invalid waitlist detection page bounds")
    try:
        policy = sources.Policy.model_validate(policy.model_dump())
        lock_institute(db, institute)
        now = utcnow()
        if not isinstance(horizon_end, datetime) or horizon_end.utcoffset() is None or horizon_end <= now:
            raise ValueError("An explicit positive future detection horizon is required")
        horizon_end = horizon_end.astimezone(timezone.utc)
        root_ids = db.scalars(select(LifecycleOriginal.root_id).where(LifecycleOriginal.institute_id == institute)
            .distinct().order_by(LifecycleOriginal.root_id))
        reviews, reasons = [], {}
        examined = active = cancelled = with_options = 0
        for root_id in root_ids:
            examined += 1
            state = lifecycle._chain(db, institute, root_id, now)
            if state.state == "cancelled":
                cancelled += 1
                continue
            event = state.events[-1]
            result = sources.read(db, institute, root_id, event.original["id"], event.fingerprint,
                horizon_end, policy, _captured_at=now)
            if result.captured_at != now or result.state != state:
                raise ValueError("Detection reviews must share captured clock and retained state")
            if result.review is not None and result.review.options:
                with_options += 1
            else:
                reason = result.unavailable_reason or (result.review.unavailable_reason if result.review else None)
                if reason is None:
                    raise ValueError("Unavailable detection requires an explicit reason")
                reasons[reason] = reasons.get(reason, 0)+1
            if offset <= active < offset+limit:
                reviews.append(result)
            active += 1
        return Detection(institute_id=institute, captured_at=now, horizon_end=horizon_end, policy=policy,
            offset=offset, limit=limit, examined_roots=examined, active=active, cancelled=cancelled,
            with_options=with_options, without_options=active-with_options,
            unavailable_reasons=reasons, reviews=tuple(reviews))
    except (ValueError, TypeError, KeyError, OverflowError) as error:
        raise business_error("Waitlist detection sources require verification") from error
