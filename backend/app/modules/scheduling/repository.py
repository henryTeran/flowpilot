"""
Repository layer for scheduling queries.

Reuses existing queries from planning, appointments, employees services.
"""

from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.appointments.models import Appointment
from app.modules.employees.models import Employee
from app.modules.planning.models import ServiceSession
from app.modules.services.models import Service
from app.modules.tickets.models import QueueTicket, TicketLine


# Reuse constants from planning service
ACTIVE_SESSION_STATUSES = ["planned", "in_progress", "extended", "delayed"]
ACTIVE_APPOINTMENT_STATUSES = ["scheduled", "confirmed", "arrived", "in_progress"]
UNAVAILABLE_EMPLOYEE_STATUSES = {"pause", "absent", "offline"}


def list_active_sessions(db: Session, institute_id: str, employee_id: str) -> list[ServiceSession]:
    return list(db.scalars(select(ServiceSession).where(
        ServiceSession.institute_id == institute_id,
        ServiceSession.employee_id == employee_id,
        ServiceSession.status.in_(ACTIVE_SESSION_STATUSES),
    ).order_by(ServiceSession.planned_end_time, ServiceSession.id)).all())


def list_remaining_appointments(db: Session, institute_id: str, employee_id: str,
                                now: datetime) -> list[Appointment]:
    return list(db.scalars(select(Appointment).where(
        Appointment.institute_id == institute_id,
        Appointment.employee_id == employee_id,
        Appointment.status.in_(ACTIVE_APPOINTMENT_STATUSES),
        Appointment.end_time > now,
    ).order_by(Appointment.start_time, Appointment.id)).all())


def get_employee_by_id(db: Session, employee_id: str) -> Employee | None:
    """Get employee record."""
    return db.get(Employee, employee_id)


def get_service_duration(db: Session, service_id: str) -> int | None:
    """Get standard service duration in minutes.
    
    Returns duration_min if available, else None.
    """
    service = db.get(Service, service_id)
    return service.duration_min if service else None


def get_active_session(
    db: Session,
    institute_id: str,
    employee_id: str,
) -> ServiceSession | None:
    """Get current active session for employee (if any).
    
    Returns the session blocking the employee, or None if available.
    """
    return db.scalars(
        select(ServiceSession)
        .where(
            ServiceSession.institute_id == institute_id,
            ServiceSession.employee_id == employee_id,
            ServiceSession.status.in_(ACTIVE_SESSION_STATUSES),
        )
        .order_by(ServiceSession.planned_end_time.desc())
    ).first()


def get_current_appointment(
    db: Session,
    institute_id: str,
    employee_id: str,
    now: datetime,
) -> Appointment | None:
    """Get appointment currently occupying employee.
    
    Only returns appointments that overlap with 'now'.
    """
    return db.scalars(
        select(Appointment)
        .where(
            Appointment.institute_id == institute_id,
            Appointment.employee_id == employee_id,
            Appointment.status.in_(ACTIVE_APPOINTMENT_STATUSES),
            Appointment.start_time <= now,
            Appointment.end_time > now,
        )
        .order_by(Appointment.end_time.asc())
    ).first()


def get_next_appointment(
    db: Session,
    institute_id: str,
    employee_id: str,
    after: datetime,
) -> Appointment | None:
    """Get next upcoming appointment for employee after 'after' time."""
    return db.scalars(
        select(Appointment)
        .where(
            Appointment.institute_id == institute_id,
            Appointment.employee_id == employee_id,
            Appointment.status.in_(ACTIVE_APPOINTMENT_STATUSES),
            Appointment.start_time >= after,
        )
        .order_by(Appointment.start_time.asc())
    ).first()


def get_upcoming_appointments(
    db: Session,
    institute_id: str,
    employee_id: str,
    after: datetime,
    limit: int = 5,
) -> list[Appointment]:
    """Get next N upcoming appointments for employee after 'after' time."""
    return list(
        db.scalars(
            select(Appointment)
            .where(
                Appointment.institute_id == institute_id,
                Appointment.employee_id == employee_id,
                Appointment.status.in_(ACTIVE_APPOINTMENT_STATUSES),
                Appointment.start_time >= after,
            )
            .order_by(Appointment.start_time.asc())
            .limit(limit)
        ).all()
    )


def list_employees_by_institute(db: Session, institute_id: str) -> list[Employee]:
    """Get all employees for institute."""
    return list(
        db.scalars(
            select(Employee)
            .where(Employee.institute_id == institute_id)
            .order_by(Employee.first_name)
        ).all()
    )


def get_waiting_ticket(db: Session, ticket_id: str) -> QueueTicket | None:
    """Get ticket (for reference)."""
    return db.get(QueueTicket, ticket_id)


def get_ticket_lines(db: Session, ticket_id: str) -> list[TicketLine]:
    """Get all service lines for a ticket."""
    return list(
        db.scalars(
            select(TicketLine).where(TicketLine.invoice_removed_at.is_(None))
            .where(TicketLine.ticket_id == ticket_id)
            .order_by(TicketLine.id)
        ).all()
    )


def get_ticket_total_duration(db: Session, ticket_id: str) -> int:
    """Calculate total duration of all services in ticket."""
    lines = get_ticket_lines(db, ticket_id)
    return sum(line.duration_minutes * line.quantity for line in lines)
