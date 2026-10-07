from datetime import timedelta
from sqlalchemy import select
from app.modules.workforce.models import EmployeeAbsence, AbsenceCancellation
from app.modules.workforce.absence_schemas import AbsenceRead, CancellationRead
from app.modules.employees.models import Employee
from app.modules.appointments.models import Appointment
from app.modules.planning.models import ServiceSession
from app.modules.scheduling.repository import ACTIVE_APPOINTMENT_STATUSES, ACTIVE_SESSION_STATUSES
from app.modules.tickets.models import QueueTicket, TicketLine
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import business_error, not_found
from app.shared.ids import new_id
from app.shared.time import utcnow, explicit_utc_instant


def active_statement(institute):
    return select(EmployeeAbsence).outerjoin(AbsenceCancellation,
        (AbsenceCancellation.institute_id == EmployeeAbsence.institute_id) & (AbsenceCancellation.absence_id == EmployeeAbsence.id)
    ).where(EmployeeAbsence.institute_id == institute, AbsenceCancellation.id.is_(None))


def remaining(db, institute, now, employee=None):
    statement = active_statement(institute).where(EmployeeAbsence.end_time > now)
    if employee is not None:
        statement = statement.where(EmployeeAbsence.employee_id == employee)
    return list(db.scalars(statement.order_by(EmployeeAbsence.start_time, EmployeeAbsence.id)))


def ensure_window(db, institute, employee, start, end):
    if db.scalar(active_statement(institute).where(EmployeeAbsence.employee_id == employee,
            EmployeeAbsence.start_time < end, EmployeeAbsence.end_time > start).limit(1)):
        raise business_error("Le creneau chevauche une absence ou un conge enregistre")


def require(db, institute, identifier):
    row = db.scalar(select(EmployeeAbsence).where(EmployeeAbsence.institute_id == institute, EmployeeAbsence.id == identifier))
    if row is None:
        raise not_found("Absence introuvable")
    return row


def snapshot(db, row):
    value = AbsenceRead.model_validate(row)
    cancelled = db.scalar(select(AbsenceCancellation).where(AbsenceCancellation.institute_id == row.institute_id, AbsenceCancellation.absence_id == row.id))
    value.cancellation = CancellationRead.model_validate(cancelled) if cancelled else None
    return value


def list_records(db, institute, employee, limit, offset):
    if employee is not None and not db.scalar(select(Employee.id).where(Employee.institute_id == institute, Employee.id == employee)):
        raise not_found("Collaboratrice introuvable")
    statement = select(EmployeeAbsence, AbsenceCancellation).outerjoin(AbsenceCancellation,
        (AbsenceCancellation.institute_id == EmployeeAbsence.institute_id) & (AbsenceCancellation.absence_id == EmployeeAbsence.id)
    ).where(EmployeeAbsence.institute_id == institute)
    if employee is not None:
        statement = statement.where(EmployeeAbsence.employee_id == employee)
    values = []
    for row, cancellation in db.execute(statement.order_by(EmployeeAbsence.start_time, EmployeeAbsence.id).limit(limit).offset(offset)):
        value = AbsenceRead.model_validate(row)
        value.cancellation = CancellationRead.model_validate(cancellation) if cancellation else None
        values.append(value)
    return values


def create(db, institute, payload, actor):
    if not isinstance(actor, str) or not actor.strip() or len(actor) > 160:
        raise business_error("Un acteur signe est requis")
    lock_institute(db, institute)
    old = db.scalar(select(EmployeeAbsence).where(EmployeeAbsence.institute_id == institute, EmployeeAbsence.idempotency_key == payload.idempotency_key))
    if old:
        facts = (old.employee_id, old.kind, explicit_utc_instant(old.start_time), explicit_utc_instant(old.end_time), old.reason, old.actor_id)
        if facts != (payload.employee_id, payload.kind, payload.start_time, payload.end_time, payload.reason, actor):
            raise business_error("La cle d'absence conserve ses conditions et son acteur originaux")
        return snapshot(db, old)
    if not db.scalar(select(Employee.id).where(Employee.institute_id == institute, Employee.id == payload.employee_id)):
        raise not_found("Collaboratrice introuvable")
    now = utcnow()
    if payload.start_time < now - timedelta(minutes=2):
        raise business_error("Une absence planifiee ne peut pas etre ajoutee retroactivement")
    ensure_window(db, institute, payload.employee_id, payload.start_time, payload.end_time)
    if db.scalar(select(Appointment.id).where(Appointment.institute_id == institute, Appointment.employee_id == payload.employee_id,
        Appointment.status.in_(ACTIVE_APPOINTMENT_STATUSES),
        ((Appointment.start_time < payload.end_time) & (Appointment.end_time > payload.start_time))
        | ((Appointment.status == "in_progress") & (Appointment.end_time <= now)))):
        raise business_error("Un rendez-vous engage occupe ce creneau")
    sessions = list(db.scalars(select(ServiceSession).where(ServiceSession.institute_id == institute, ServiceSession.employee_id == payload.employee_id,
                                                          ServiceSession.status.in_(ACTIVE_SESSION_STATUSES))))
    if any(explicit_utc_instant(session.planned_end_time) <= now or (explicit_utc_instant(session.start_time) < payload.end_time
           and explicit_utc_instant(session.planned_end_time) > payload.start_time) for session in sessions):
        raise business_error("Une prestation active ou de duree restante inconnue occupe cette collaboratrice")
    minutes = sum(minutes * quantity for minutes, quantity in db.execute(select(TicketLine.duration_minutes, TicketLine.quantity)
        .join(QueueTicket, QueueTicket.id == TicketLine.ticket_id).where(QueueTicket.institute_id == institute,
        QueueTicket.assigned_employee_id == payload.employee_id, QueueTicket.status == "assigned", TicketLine.invoice_removed_at.is_(None))))
    if minutes and now < payload.end_time and now + timedelta(minutes=minutes) > payload.start_time:
        raise business_error("Un ticket affecte reserve ce creneau")
    row = EmployeeAbsence(id=new_id("abs"), institute_id=institute, **payload.model_dump(), actor_id=actor, created_at=now)
    db.add(row); db.commit(); db.refresh(row)
    return snapshot(db, row)


def cancel(db, institute, identifier, payload, actor):
    if not isinstance(actor, str) or not actor.strip() or len(actor) > 160:
        raise business_error("Un acteur signe est requis")
    lock_institute(db, institute)
    old = db.scalar(select(AbsenceCancellation).where(AbsenceCancellation.institute_id == institute, AbsenceCancellation.idempotency_key == payload.idempotency_key))
    if old:
        if (old.absence_id, old.reason, old.actor_id) != (identifier, payload.reason, actor):
            raise business_error("La cle d'annulation conserve ses conditions originales")
        return CancellationRead.model_validate(old)
    require(db, institute, identifier)
    if db.scalar(select(AbsenceCancellation.id).where(AbsenceCancellation.institute_id == institute, AbsenceCancellation.absence_id == identifier)):
        raise business_error("Cette absence a deja son annulation originale")
    row = AbsenceCancellation(id=new_id("ac"), institute_id=institute, absence_id=identifier, **payload.model_dump(), actor_id=actor, created_at=utcnow())
    db.add(row); db.commit(); db.refresh(row)
    return CancellationRead.model_validate(row)
