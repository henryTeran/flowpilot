from datetime import datetime, time, timezone
from math import ceil

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.employees.repository import list_by_institute
from app.modules.planning.models import ServiceSession
from app.modules.planning.repository import list_sessions_for_day
from app.modules.planning.service import get_institute_availability
from app.modules.tickets.models import QueueTicket
from app.modules.dashboard.schemas import InstituteDashboardRead
from app.shared.time import utcnow


ACTIVE_SESSION_STATUSES = {"planned", "in_progress", "extended", "delayed"}
COMPLETED_SESSION_STATUSES = {"completed"}


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _today_bounds(now: datetime) -> tuple[datetime, datetime]:
    start = datetime.combine(now.date(), time.min, tzinfo=now.tzinfo)
    end = datetime.combine(now.date(), time.max, tzinfo=now.tzinfo)
    return start, end


def _is_session_late(session: ServiceSession, now: datetime) -> bool:
    return session.status in ACTIVE_SESSION_STATUSES and _ensure_aware(session.planned_end_time) <= now


def _average_wait_minutes(tickets: list[QueueTicket], now: datetime) -> int | None:
    waiting_like = [ticket for ticket in tickets if ticket.status in {"waiting", "assigned"}]
    if not waiting_like:
        return None

    waits: list[int] = []
    for ticket in waiting_like:
        if ticket.estimated_start_time:
            target = _ensure_aware(ticket.estimated_start_time)
            waits.append(max(0, ceil((target - now).total_seconds() / 60)))
        else:
            arrival = _ensure_aware(ticket.arrival_time)
            waits.append(max(0, ceil((now - arrival).total_seconds() / 60)))

    return round(sum(waits) / len(waits)) if waits else None


def get_institute_dashboard(db: Session, institute_id: str) -> InstituteDashboardRead:
    """
    Dashboard institut MVP.

    Il agrège uniquement les données opérationnelles déjà disponibles dans le MVP :
    tickets, sessions planning, statuts collaboratrices et disponibilité live.
    """
    now = utcnow()
    start_day, end_day = _today_bounds(now)

    employees = list_by_institute(db, institute_id)
    sessions_today = list_sessions_for_day(db, institute_id, now)
    tickets_today = list(
        db.scalars(
            select(QueueTicket)
            .where(
                QueueTicket.institute_id == institute_id,
                QueueTicket.arrival_time >= start_day,
                QueueTicket.arrival_time <= end_day,
            )
            .order_by(QueueTicket.arrival_time)
        ).all()
    )

    active_sessions = [session for session in sessions_today if session.status in ACTIVE_SESSION_STATUSES]
    delayed_sessions = [session for session in active_sessions if _is_session_late(session, now) or session.status == "delayed"]
    completed_sessions = [session for session in sessions_today if session.status in COMPLETED_SESSION_STATUSES]

    employee_statuses = {employee.id: employee.status for employee in employees}

    # Une collaboratrice avec une session dépassée doit être vue comme en retard côté dashboard,
    # même si son champ status est resté disponible par erreur.
    delayed_employee_ids = {session.employee_id for session in delayed_sessions}

    employees_available = sum(1 for employee in employees if employee.status == "available" and employee.id not in delayed_employee_ids)
    employees_busy = sum(1 for employee in employees if employee.status == "busy" and employee.id not in delayed_employee_ids)
    employees_pause = sum(1 for employee in employees if employee.status == "pause")
    employees_absent_or_offline = sum(1 for employee in employees if employee.status in {"absent", "offline"})

    tickets_by_status = {status: 0 for status in ["waiting", "assigned", "in_progress", "completed", "cancelled"]}
    for ticket in tickets_today:
        if ticket.status in tickets_by_status:
            tickets_by_status[ticket.status] += 1

    availability = get_institute_availability(db, institute_id)
    average_wait = _average_wait_minutes(tickets_today, now)

    if delayed_sessions:
        operational_status = "alert"
        alert_message = f"{len(delayed_sessions)} prestation(s) en retard à clôturer."
    elif tickets_by_status["waiting"] + tickets_by_status["assigned"] >= 4:
        operational_status = "busy"
        alert_message = "File d’attente chargée : renforcer la vigilance à l’accueil."
    elif active_sessions:
        operational_status = "normal"
        alert_message = None
    else:
        operational_status = "calm"
        alert_message = None

    return InstituteDashboardRead(
        institute_id=institute_id,
        generated_at=now,
        employees_total=len(employees),
        employees_available=employees_available,
        employees_busy=employees_busy,
        employees_delayed=len(delayed_employee_ids),
        employees_pause=employees_pause,
        employees_absent_or_offline=employees_absent_or_offline,
        tickets_waiting=tickets_by_status["waiting"],
        tickets_assigned=tickets_by_status["assigned"],
        tickets_in_progress=tickets_by_status["in_progress"],
        tickets_completed_today=tickets_by_status["completed"],
        tickets_cancelled_today=tickets_by_status["cancelled"],
        sessions_active=len(active_sessions),
        sessions_delayed=len(delayed_sessions),
        sessions_completed_today=len(completed_sessions),
        average_wait_minutes=average_wait,
        next_available_employee_name=availability.next_employee_name,
        next_available_minutes=availability.wait_minutes,
        operational_status=operational_status,
        alert_message=alert_message,
    )
