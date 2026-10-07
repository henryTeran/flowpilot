from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from sqlalchemy import and_, case, func, select
from app.modules.employees.models import Employee
from app.modules.institutes.models import Institute
from app.modules.institutes.calendar import day_bounds
from app.modules.planning.models import ServiceSession
from app.modules.tickets.models import QueueTicket, TicketLine
from app.modules.tickets.repository import lock_institute
from app.modules.workforce.models import EmployeeObjective, ObjectiveCancellation
from app.modules.workforce.objective_schemas import ObjectiveRead, CancellationRead
from app.modules.workforce.certifications import signed_actor
from app.modules.workforce.revenue import closed_line_conditions
from app.shared.exceptions import business_error, not_found
from app.shared.ids import new_id
from app.shared.time import utcnow


def require_employee(db, institute, employee):
    if not db.scalar(select(Employee.id).where(Employee.institute_id == institute, Employee.id == employee)):
        raise not_found("Collaboratrice introuvable")


def require(db, institute, identifier):
    row = db.scalar(select(EmployeeObjective).where(EmployeeObjective.institute_id == institute, EmployeeObjective.id == identifier))
    if row is None:
        raise not_found("Objectif introuvable")
    return row


def snapshot(db, row):
    result = ObjectiveRead.model_validate(row)
    cancellation = db.scalar(select(ObjectiveCancellation).where(ObjectiveCancellation.institute_id == row.institute_id,
                                                               ObjectiveCancellation.objective_id == row.id))
    result.cancellation = CancellationRead.model_validate(cancellation) if cancellation else None
    return result


def create(db, institute, payload, actor):
    signed_actor(actor)
    lock_institute(db, institute)
    old = db.scalar(select(EmployeeObjective).where(EmployeeObjective.institute_id == institute,
                                                  EmployeeObjective.idempotency_key == payload.idempotency_key))
    if old:
        terms = ObjectiveRead.model_validate(old).model_dump(include=set(type(payload).model_fields))
        if old.actor_id != actor or terms != payload.model_dump():
            raise business_error("La cle conserve les conditions et l'acteur originaux")
        return snapshot(db, old)
    require_employee(db, institute, payload.employee_id)
    start = day_bounds(db, institute, payload.first_day)[0]
    end = day_bounds(db, institute, payload.last_day)[1]
    if end <= start:
        raise business_error("La periode ne contient aucun instant")
    try:
        zone = ZoneInfo(db.get(Institute, institute).timezone).key
    except (ZoneInfoNotFoundError, ValueError):
        zone = "UTC"
    values = payload.model_dump()
    values["target"] = format(payload.target, "f")
    if "." in values["target"]:
        values["target"] = values["target"].rstrip("0").rstrip(".")
    row = EmployeeObjective(id=new_id("obj"), institute_id=institute, **values, timezone=zone,
                            period_start=start, period_end=end, actor_id=actor, created_at=utcnow())
    db.add(row); db.commit(); db.refresh(row)
    return snapshot(db, row)


def cancel(db, institute, identifier, payload, actor):
    signed_actor(actor)
    lock_institute(db, institute)
    old = db.scalar(select(ObjectiveCancellation).where(ObjectiveCancellation.institute_id == institute,
                                                       ObjectiveCancellation.idempotency_key == payload.idempotency_key))
    if old:
        if (old.objective_id, old.reason, old.actor_id) != (identifier, payload.reason, actor):
            raise business_error("La cle conserve les conditions et l'acteur originaux")
        return CancellationRead.model_validate(old)
    require(db, institute, identifier)
    if db.scalar(select(ObjectiveCancellation.id).where(ObjectiveCancellation.institute_id == institute,
                                                        ObjectiveCancellation.objective_id == identifier)):
        raise business_error("Cet objectif a deja son annulation originale")
    row = ObjectiveCancellation(id=new_id("ocn"), institute_id=institute, objective_id=identifier,
                                 **payload.model_dump(), actor_id=actor, created_at=utcnow())
    db.add(row); db.commit(); db.refresh(row)
    return CancellationRead.model_validate(row)


def progress_facts(db, institute, ids, now):
    if not ids:
        return {}
    obj = EmployeeObjective
    facts = {}
    gross = select(obj.id, func.count(TicketLine.id),
        func.sum(case((QueueTicket.currency == obj.currency, TicketLine.total), else_=Decimal("0.00"))),
        func.sum(case(((QueueTicket.currency == obj.currency) & TicketLine.total.is_(None) & TicketLine.id.is_not(None), 1), else_=0)),
        func.sum(case((QueueTicket.currency.is_(None) & TicketLine.id.is_not(None), 1), else_=0)),
        func.sum(case(((QueueTicket.currency != obj.currency) & TicketLine.id.is_not(None), 1), else_=0)))
    gross = gross.select_from(obj).outerjoin(QueueTicket, (QueueTicket.institute_id == obj.institute_id)
        & (QueueTicket.status == "paid") & (QueueTicket.paid_at >= obj.period_start)
        & (QueueTicket.paid_at < obj.period_end) & (QueueTicket.paid_at <= now))
    gross = gross.outerjoin(TicketLine, (TicketLine.ticket_id == QueueTicket.id)
        & (TicketLine.performed_by_employee_id == obj.employee_id)
        & and_(*closed_line_conditions(obj.institute_id, obj.period_start, obj.period_end))).where(obj.institute_id == institute,
            obj.id.in_(ids), obj.metric == "closed_attributed_gross").group_by(obj.id)
    for identifier, count, known, missing, unknown, other in db.execute(gross):
        facts[identifier] = (count, known or Decimal("0.00"), missing, unknown, other)
    sessions = select(obj.id, func.count(ServiceSession.id)).select_from(obj).outerjoin(ServiceSession,
        (ServiceSession.institute_id == obj.institute_id) & (ServiceSession.employee_id == obj.employee_id)
        & (ServiceSession.status == "completed") & (ServiceSession.real_end_time >= obj.period_start)
        & (ServiceSession.real_end_time < obj.period_end) & (ServiceSession.real_end_time <= now)
        & (ServiceSession.start_time <= ServiceSession.real_end_time)).where(obj.institute_id == institute,
            obj.id.in_(ids), obj.metric == "completed_sessions").group_by(obj.id)
    for identifier, count in db.execute(sessions):
        facts[identifier] = (count, Decimal(count), 0, 0, 0)
    return facts


def list_records(db, institute, employee, limit=20, offset=0):
    lock_institute(db, institute)
    require_employee(db, institute, employee)
    predicate = (EmployeeObjective.institute_id == institute, EmployeeObjective.employee_id == employee)
    total = db.scalar(select(func.count()).select_from(EmployeeObjective).where(*predicate))
    records = list(db.execute(select(EmployeeObjective, ObjectiveCancellation).outerjoin(ObjectiveCancellation,
        (ObjectiveCancellation.institute_id == EmployeeObjective.institute_id)
        & (ObjectiveCancellation.objective_id == EmployeeObjective.id)).where(*predicate)
        .order_by(EmployeeObjective.period_start, EmployeeObjective.id).limit(limit).offset(offset)))
    now = utcnow()
    facts = progress_facts(db, institute, [row.id for row, cancellation in records if not cancellation], now)
    values = []
    for row, cancellation in records:
        original = ObjectiveRead.model_validate(row)
        original.cancellation = CancellationRead.model_validate(cancellation) if cancellation else None
        count, known, missing, unknown, other = facts.get(row.id, (0, Decimal("0.00"), 0, 0, 0))
        state = "cancelled" if cancellation else "upcoming" if now < original.period_start else "ended" if now >= original.period_end else "active"
        value = None if cancellation or missing or unknown else known
        values.append(dict(objective=original, period_state=state, known_value=None if cancellation else known, value=value,
            achieved=value >= original.target if value is not None else None, source_count=None if cancellation else count,
            missing_amount_sources=None if cancellation else missing, unknown_currency_sources=None if cancellation else unknown,
            other_currency_sources=None if cancellation else other))
    return dict(institute_id=institute, employee_id=employee, generated_at=now,
                page=dict(offset=offset, limit=limit, total=total), rows=values)
