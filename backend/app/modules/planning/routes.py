from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
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
    get_day_planning,
    get_institute_availability,
    start_service_session,
)

router = APIRouter(prefix="/planning", tags=["planning"])


@router.get("/institutes/{institute_id}/today", response_model=PlanningDayRead)
def get_today_planning(institute_id: str, db: Session = Depends(get_db)) -> PlanningDayRead:
    return get_day_planning(db, institute_id)


@router.get("/institutes/{institute_id}/availability", response_model=PlanningAvailabilityRead)
def get_availability(institute_id: str, db: Session = Depends(get_db)) -> PlanningAvailabilityRead:
    return get_institute_availability(db, institute_id)


@router.post("/sessions/start", response_model=ServiceSessionRead)
def post_start_session(payload: StartSession, db: Session = Depends(get_db)) -> ServiceSessionRead:
    return start_service_session(db, payload.ticket_id, payload.employee_id, payload.service_id)


@router.patch("/sessions/{session_id}/finish", response_model=ServiceSessionRead)
def patch_finish_session(session_id: str, db: Session = Depends(get_db)) -> ServiceSessionRead:
    return finish_service_session(db, session_id)


@router.patch("/sessions/{session_id}/extend", response_model=ServiceSessionRead)
def patch_extend_session(
    session_id: str,
    payload: ExtendSession,
    db: Session = Depends(get_db),
) -> ServiceSessionRead:
    return extend_service_session(db, session_id, payload.minutes)
