from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from sqlalchemy import func, select
from app.modules.employees.models import Employee
from app.modules.institutes.models import Institute
from app.modules.institutes.calendar import day_bounds
from app.modules.tickets.repository import lock_institute
from app.modules.workforce.models import EmployeeCommissionRule, CommissionRuleCancellation
from app.modules.workforce.commission_rule_schemas import CommissionRuleRead, CancellationRead
from app.modules.workforce.certifications import signed_actor
from app.modules.services.models import Service
from app.shared.exceptions import business_error, not_found
from app.shared.ids import new_id
from app.shared.time import utcnow, explicit_utc_instant


def require_employee(db, institute, employee):
    if not db.scalar(select(Employee.id).where(Employee.institute_id == institute, Employee.id == employee)):
        raise not_found("Collaboratrice introuvable")


def require(db, institute, identifier):
    row = db.scalar(select(EmployeeCommissionRule).where(EmployeeCommissionRule.institute_id == institute, EmployeeCommissionRule.id == identifier))
    if row is None:
        raise not_found("Regle de commission introuvable")
    return row


def snapshot(db, row):
    result = CommissionRuleRead.model_validate(row)
    cancellation = db.scalar(select(CommissionRuleCancellation).where(CommissionRuleCancellation.institute_id == row.institute_id,
                                                               CommissionRuleCancellation.rule_id == row.id))
    result.cancellation = CancellationRead.model_validate(cancellation) if cancellation else None
    return result


def create(db, institute, payload, actor):
    signed_actor(actor)
    lock_institute(db, institute)
    old = db.scalar(select(EmployeeCommissionRule).where(EmployeeCommissionRule.institute_id == institute,
                                                  EmployeeCommissionRule.idempotency_key == payload.idempotency_key))
    if old:
        terms = CommissionRuleRead.model_validate(old).model_dump(include=set(type(payload).model_fields))
        if old.actor_id != actor or terms != payload.model_dump():
            raise business_error("La cle conserve les conditions et l'acteur originaux")
        return snapshot(db, old)
    require_employee(db, institute, payload.employee_id)
    if payload.service_id is not None and db.get(Service, payload.service_id) is None:
        raise not_found("Service introuvable")
    start = day_bounds(db, institute, payload.first_day)[0]
    end = day_bounds(db, institute, payload.last_day)[1]
    if end <= start:
        raise business_error("La periode ne contient aucun instant")
    try:
        zone = ZoneInfo(db.get(Institute, institute).timezone).key
    except (ZoneInfoNotFoundError, ValueError):
        zone = "UTC"
    values = payload.model_dump()
    row = EmployeeCommissionRule(id=new_id("crl"), institute_id=institute, **values, timezone=zone,
                            period_start=start, period_end=end, actor_id=actor, created_at=utcnow())
    db.add(row); db.commit(); db.refresh(row)
    return snapshot(db, row)


def cancel(db, institute, identifier, payload, actor):
    signed_actor(actor)
    lock_institute(db, institute)
    old = db.scalar(select(CommissionRuleCancellation).where(CommissionRuleCancellation.institute_id == institute,
                                                       CommissionRuleCancellation.idempotency_key == payload.idempotency_key))
    if old:
        if (old.rule_id, old.reason, old.actor_id) != (identifier, payload.reason, actor):
            raise business_error("La cle conserve les conditions et l'acteur originaux")
        return CancellationRead.model_validate(old)
    original = require(db, institute, identifier)
    if db.scalar(select(CommissionRuleCancellation.id).where(CommissionRuleCancellation.institute_id == institute,
                                                        CommissionRuleCancellation.rule_id == identifier)):
        raise business_error("Cette regle de commission a deja son annulation originale")
    now = utcnow()
    if now < explicit_utc_instant(original.created_at):
        raise business_error("L'horloge d'annulation precede la regle originale")
    row = CommissionRuleCancellation(id=new_id("crc"), institute_id=institute, rule_id=identifier,
                                 **payload.model_dump(), actor_id=actor, created_at=now)
    db.add(row); db.commit(); db.refresh(row)
    return CancellationRead.model_validate(row)


def original(db, institute, key):
    row = db.scalar(select(EmployeeCommissionRule).where(EmployeeCommissionRule.institute_id == institute,
        EmployeeCommissionRule.idempotency_key == key))
    return snapshot(db, row) if row else None


def list_records(db, institute, employee, limit=20, offset=0):
    lock_institute(db, institute)
    require_employee(db, institute, employee)
    predicate = (EmployeeCommissionRule.institute_id == institute, EmployeeCommissionRule.employee_id == employee)
    total = db.scalar(select(func.count()).select_from(EmployeeCommissionRule).where(*predicate))
    rows = db.execute(select(EmployeeCommissionRule, CommissionRuleCancellation).outerjoin(CommissionRuleCancellation,
        (CommissionRuleCancellation.institute_id == EmployeeCommissionRule.institute_id)
        & (CommissionRuleCancellation.rule_id == EmployeeCommissionRule.id)).where(*predicate)
        .order_by(EmployeeCommissionRule.period_start, EmployeeCommissionRule.id).limit(limit).offset(offset))
    values = [CommissionRuleRead.model_validate(row).model_copy(update={"cancellation":
        CancellationRead.model_validate(cancelled) if cancelled else None}) for row, cancelled in rows]
    return dict(institute_id=institute, employee_id=employee, generated_at=utcnow(),
        page=dict(limit=limit, offset=offset, total=total), rows=values)
