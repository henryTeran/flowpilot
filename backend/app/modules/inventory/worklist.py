"""Bounded completed work; detail remains available for original recovery."""
from sqlalchemy import select, literal, union_all, and_
from app.modules.inventory.models import StockServiceBasis as Basis, StockConsumption
from app.modules.inventory import consumptions
from app.modules.inventory.schemas import ConsumptionWorkDetail
from app.modules.planning.models import ServiceSession
from app.modules.appointments.models import Appointment
from app.modules.services.models import Service
from app.modules.employees.models import Employee
from app.modules.tickets.models import TicketLine, QueueTicket
from app.shared.exceptions import not_found


def query(institute, *, completed_only):
    parts = []
    for model, source_field, kind, end_field in (
        (ServiceSession, Basis.session_id, "sessions", ServiceSession.real_end_time),
        (Appointment, Basis.appointment_id, "appointments", Appointment.actual_end_time)):
        statement = select(Basis.id.label("basis_id"), Basis.institute_id, literal(kind).label("source_kind"),
            model.id.label("source_id"), model.status.label("source_status"), Basis.service_id,
            Employee.first_name.label("employee_name"),
            (QueueTicket.ticket_number if kind == "sessions" else literal(None)).label("ticket_number"),
            Service.name.label("service_name"), Basis.quantity, Basis.state, Basis.captured_at,
            end_field.label("completed_at"), StockConsumption.id.label("consumption_id")).join(
                model, and_(source_field == model.id, Basis.institute_id == model.institute_id)).join(
                Service, Service.id == Basis.service_id).join(Employee, and_(
                Employee.id == model.employee_id, Employee.institute_id == Basis.institute_id)).outerjoin(StockConsumption,
                and_(StockConsumption.basis_id == Basis.id, StockConsumption.institute_id == Basis.institute_id)).where(
                Basis.institute_id == institute)
        if kind == "sessions":
            statement = statement.outerjoin(TicketLine, TicketLine.id == Basis.ticket_line_id).outerjoin(
                QueueTicket, and_(QueueTicket.id == TicketLine.ticket_id, QueueTicket.institute_id == Basis.institute_id))
        if completed_only:
            statement = statement.where(model.status == "completed")
        parts.append(statement)
    return union_all(*parts).subquery()


def list_work(db, institute, state, limit, offset):
    work = query(institute, completed_only=True)
    statement = select(work)
    if state != "all":
        statement = statement.where(work.c.consumption_id.is_(None) if state == "pending" else work.c.consumption_id.is_not(None))
    return db.execute(statement.order_by(work.c.captured_at.desc(), work.c.basis_id).limit(limit).offset(offset)).mappings().all()


def detail(db, institute, basis_id):
    work = query(institute, completed_only=False)
    row = db.execute(select(work).where(work.c.basis_id == basis_id)).mappings().first()
    if row is None:
        raise not_found("Base d'execution introuvable")
    basis = consumptions.require_basis(db, institute, basis_id)
    original = db.get(StockConsumption, row["consumption_id"]) if row["consumption_id"] else None
    return ConsumptionWorkDetail(**row, expected_entries=consumptions.expected(db, basis),
        consumption=consumptions.snapshot(db, original) if original else None)
