from sqlalchemy import select, func
from app.modules.workforce.models import EmployeeWorkInterval, WorkIntervalCancellation
from app.modules.workforce.work_interval_schemas import WorkIntervalRead, WorkIntervalCancellationRead
from app.modules.workforce.objectives import require_employee
from app.modules.workforce.certifications import signed_actor
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import business_error, not_found
from app.shared.ids import new_id
from app.shared.time import utcnow


def require(db, institute, identifier):
    row = db.scalar(select(EmployeeWorkInterval).where(EmployeeWorkInterval.institute_id == institute, EmployeeWorkInterval.id == identifier))
    if row is None:
        raise not_found("Intervalle de travail introuvable")
    return row


def snapshot(db, row):
    result = WorkIntervalRead.model_validate(row)
    cancellation = db.scalar(select(WorkIntervalCancellation).where(WorkIntervalCancellation.institute_id == row.institute_id,
                                                                   WorkIntervalCancellation.work_interval_id == row.id))
    result.cancellation = WorkIntervalCancellationRead.model_validate(cancellation) if cancellation else None
    return result


def create(db, institute, payload, actor):
    signed_actor(actor)
    lock_institute(db, institute)
    old = db.scalar(select(EmployeeWorkInterval).where(EmployeeWorkInterval.institute_id == institute,
                                                       EmployeeWorkInterval.idempotency_key == payload.idempotency_key))
    if old:
        terms = WorkIntervalRead.model_validate(old).model_dump(include=set(type(payload).model_fields))
        if old.actor_id != actor or terms != payload.model_dump():
            raise business_error("La cle conserve les conditions et l'acteur originaux")
        return snapshot(db, old)
    require_employee(db, institute, payload.employee_id)
    now = utcnow()
    if payload.end_time > now:
        raise business_error("Les heures effectives ne peuvent avoir une fin future")
    overlap = select(EmployeeWorkInterval.id).outerjoin(WorkIntervalCancellation,
        (WorkIntervalCancellation.institute_id == EmployeeWorkInterval.institute_id)
        & (WorkIntervalCancellation.work_interval_id == EmployeeWorkInterval.id)).where(
            EmployeeWorkInterval.institute_id == institute, EmployeeWorkInterval.employee_id == payload.employee_id,
            WorkIntervalCancellation.id.is_(None), EmployeeWorkInterval.start_time < payload.end_time,
            EmployeeWorkInterval.end_time > payload.start_time).limit(1)
    if db.scalar(overlap):
        raise business_error("L'intervalle chevauche des heures effectives non annulees")
    row = EmployeeWorkInterval(id=new_id("wrk"), institute_id=institute, **payload.model_dump(), actor_id=actor, created_at=now)
    db.add(row); db.commit(); db.refresh(row)
    return snapshot(db, row)


def cancel(db, institute, identifier, payload, actor):
    signed_actor(actor)
    lock_institute(db, institute)
    old = db.scalar(select(WorkIntervalCancellation).where(WorkIntervalCancellation.institute_id == institute,
                                                         WorkIntervalCancellation.idempotency_key == payload.idempotency_key))
    if old:
        if (old.work_interval_id, old.reason, old.actor_id) != (identifier, payload.reason, actor):
            raise business_error("La cle conserve les conditions et l'acteur originaux")
        return WorkIntervalCancellationRead.model_validate(old)
    require(db, institute, identifier)
    if db.scalar(select(WorkIntervalCancellation.id).where(WorkIntervalCancellation.institute_id == institute,
                                                          WorkIntervalCancellation.work_interval_id == identifier)):
        raise business_error("Cet intervalle a deja son annulation originale")
    row = WorkIntervalCancellation(id=new_id("wcn"), institute_id=institute, work_interval_id=identifier,
                                  **payload.model_dump(), actor_id=actor, created_at=utcnow())
    db.add(row); db.commit(); db.refresh(row)
    return WorkIntervalCancellationRead.model_validate(row)


def list_records(db, institute, employee, limit=20, offset=0):
    lock_institute(db, institute)
    require_employee(db, institute, employee)
    predicate = (EmployeeWorkInterval.institute_id == institute, EmployeeWorkInterval.employee_id == employee)
    total = db.scalar(select(func.count()).select_from(EmployeeWorkInterval).where(*predicate))
    records = db.execute(select(EmployeeWorkInterval, WorkIntervalCancellation).outerjoin(WorkIntervalCancellation,
        (WorkIntervalCancellation.institute_id == EmployeeWorkInterval.institute_id)
        & (WorkIntervalCancellation.work_interval_id == EmployeeWorkInterval.id)).where(*predicate)
        .order_by(EmployeeWorkInterval.start_time, EmployeeWorkInterval.id).limit(limit).offset(offset))
    rows = []
    for original, cancellation in records:
        value = WorkIntervalRead.model_validate(original)
        value.cancellation = WorkIntervalCancellationRead.model_validate(cancellation) if cancellation else None
        rows.append(value)
    return dict(institute_id=institute, employee_id=employee, generated_at=utcnow(),
                page=dict(offset=offset, limit=limit, total=total), rows=rows)
