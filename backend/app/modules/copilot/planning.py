"""Minimal projections of existing planning and scheduling services."""
from pydantic import AwareDatetime
from typing import Literal
from app.modules.base import query as base_query
from app.modules.crm.metrics import Fact
from app.modules.scheduling import service as scheduling
from app.modules.planning import service as planning
from app.shared.time import explicit_utc_instant


class Gaps(Fact):
    captured_at: AwareDatetime
    rows: tuple[base_query.AvailabilityFacts, ...]
    basis: Literal["current_scheduling_engine_windows"] = "current_scheduling_engine_windows"
    complete_work_hours: Literal[False] = False
    booking_authorized: Literal[False] = False


def read_day(db, institute):
    value = planning.get_day_planning(db, institute)
    return base_query.PlanningFacts(generated_at=explicit_utc_instant(value.generated_at), rows=tuple(
        base_query.PlanningRow(employee_id=row.employee_id, employee_status=row.employee_status, sessions=tuple(
            base_query.SessionFact(id=s.id, employee_id=s.employee_id, service_id=s.service_id,
                start_time=explicit_utc_instant(s.start_time), planned_end_time=explicit_utc_instant(s.planned_end_time), status=s.status)
            for s in row.sessions)) for row in value.rows))


def read_gaps(db, institute, service, captured):
    rows = scheduling.availability_pool(db, institute, service, now=captured)
    return Gaps(captured_at=captured, rows=tuple(base_query.AvailabilityFacts.model_validate(row.to_dict()) for row in rows))
