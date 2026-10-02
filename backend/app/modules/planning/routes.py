from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.permissions import require_same_institute, require_ticket_manager
from app.database.session import get_db
from app.modules.planning.repository import get_session
from app.modules.planning.schemas import (
    ExtendSession,
    PlanningAvailabilityRead,
    PlanningDayRead,
    ServiceSessionRead,
    StartSession,
)
from app.modules.planning.service import (
    extend_service_session,
    finish_service_session,
    finish_active_employee_session,
    get_day_planning,
    get_institute_availability,
    start_service_session,
)
from app.modules.tickets.repository import get_ticket

router = APIRouter(prefix="/planning", tags=["planning"])


def _require_ticket_scope(
    ticket_id: str,
    current_user: dict[str, str | None],
    db: Session,
) -> None:
    ticket = get_ticket(db, ticket_id)
    if ticket:
        require_same_institute(current_user, ticket.institute_id)


def _require_session_scope(
    session_id: str,
    current_user: dict[str, str | None],
    db: Session,
) -> None:
    session = get_session(db, session_id)
    if session:
        require_same_institute(current_user, session.institute_id)


@router.get("/institutes/{institute_id}/today", response_model=PlanningDayRead)
def get_today_planning(
    institute_id: str,
    current_user: dict[str, str | None] = Depends(require_ticket_manager),
    db: Session = Depends(get_db),
) -> PlanningDayRead:
    require_same_institute(current_user, institute_id)
    return get_day_planning(db, institute_id)


@router.get("/institutes/{institute_id}/availability", response_model=PlanningAvailabilityRead)
def get_availability(
    institute_id: str,
    current_user: dict[str, str | None] = Depends(require_ticket_manager),
    db: Session = Depends(get_db),
) -> PlanningAvailabilityRead:
    require_same_institute(current_user, institute_id)
    return get_institute_availability(db, institute_id)


@router.post("/sessions/start", response_model=ServiceSessionRead)
def post_start_session(
    payload: StartSession,
    current_user: dict[str, str | None] = Depends(require_ticket_manager),
    db: Session = Depends(get_db),
) -> ServiceSessionRead:
    _require_ticket_scope(payload.ticket_id, current_user, db)
    return start_service_session(db, payload.ticket_id, payload.employee_id, payload.service_id)


@router.patch("/sessions/{session_id}/finish", response_model=ServiceSessionRead)
def patch_finish_session(
    session_id: str,
    current_user: dict[str, str | None] = Depends(require_ticket_manager),
    db: Session = Depends(get_db),
) -> ServiceSessionRead:
    _require_session_scope(session_id, current_user, db)
    return finish_service_session(db, session_id)


@router.patch("/institutes/{institute_id}/employees/{employee_id}/finish-active-session", response_model=ServiceSessionRead)
def patch_finish_active_employee_session(
    institute_id: str,
    employee_id: str,
    current_user: dict[str, str | None] = Depends(require_ticket_manager),
    db: Session = Depends(get_db),
) -> ServiceSessionRead:
    require_same_institute(current_user, institute_id)
    return finish_active_employee_session(db, institute_id, employee_id)


@router.patch("/sessions/{session_id}/extend", response_model=ServiceSessionRead)
def patch_extend_session(
    session_id: str,
    payload: ExtendSession,
    current_user: dict[str, str | None] = Depends(require_ticket_manager),
    db: Session = Depends(get_db),
) -> ServiceSessionRead:
    _require_session_scope(session_id, current_user, db)
    return extend_service_session(db, session_id, payload.minutes)
