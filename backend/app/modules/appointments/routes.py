from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.permissions import require_same_institute, require_ticket_manager
from app.database.session import get_db
from app.modules.appointments.repository import get_appointment
from app.modules.appointments.schemas import AppointmentCreate, AppointmentRead
from app.modules.appointments.service import (
    cancel_appointment,
    complete_appointment,
    create_appointment,
    list_today_appointments,
    mark_appointment_arrived,
    mark_appointment_no_show,
    start_appointment,
)

router = APIRouter(prefix="/appointments", tags=["appointments"])


def _require_appointment_access(
    appointment_id: str,
    current_user: dict[str, str | None],
    db: Session,
) -> None:
    appointment = get_appointment(db, appointment_id)
    if appointment:
        require_same_institute(current_user, appointment.institute_id)


@router.get("", response_model=list[AppointmentRead])
def get_appointments(
    institute_id: str,
    current_user: dict[str, str | None] = Depends(require_ticket_manager),
    db: Session = Depends(get_db),
) -> list[AppointmentRead]:
    require_same_institute(current_user, institute_id)
    return list_today_appointments(db, institute_id)


@router.post("", response_model=AppointmentRead)
def post_appointment(
    payload: AppointmentCreate,
    current_user: dict[str, str | None] = Depends(require_ticket_manager),
    db: Session = Depends(get_db),
) -> AppointmentRead:
    require_same_institute(current_user, payload.institute_id)
    return create_appointment(db, payload)


@router.patch("/{appointment_id}/arrive", response_model=AppointmentRead)
def patch_appointment_arrived(
    appointment_id: str,
    current_user: dict[str, str | None] = Depends(require_ticket_manager),
    db: Session = Depends(get_db),
) -> AppointmentRead:
    _require_appointment_access(appointment_id, current_user, db)
    return mark_appointment_arrived(db, appointment_id)


@router.patch("/{appointment_id}/start", response_model=AppointmentRead)
def patch_start_appointment(
    appointment_id: str,
    current_user: dict[str, str | None] = Depends(require_ticket_manager),
    db: Session = Depends(get_db),
) -> AppointmentRead:
    _require_appointment_access(appointment_id, current_user, db)
    return start_appointment(db, appointment_id)


@router.patch("/{appointment_id}/complete", response_model=AppointmentRead)
def patch_complete_appointment(
    appointment_id: str,
    current_user: dict[str, str | None] = Depends(require_ticket_manager),
    db: Session = Depends(get_db),
) -> AppointmentRead:
    _require_appointment_access(appointment_id, current_user, db)
    return complete_appointment(db, appointment_id)


@router.patch("/{appointment_id}/no-show", response_model=AppointmentRead)
def patch_no_show_appointment(
    appointment_id: str,
    current_user: dict[str, str | None] = Depends(require_ticket_manager),
    db: Session = Depends(get_db),
) -> AppointmentRead:
    _require_appointment_access(appointment_id, current_user, db)
    return mark_appointment_no_show(db, appointment_id)


@router.patch("/{appointment_id}/cancel", response_model=AppointmentRead)
def patch_cancel_appointment(
    appointment_id: str,
    current_user: dict[str, str | None] = Depends(require_ticket_manager),
    db: Session = Depends(get_db),
) -> AppointmentRead:
    _require_appointment_access(appointment_id, current_user, db)
    return cancel_appointment(db, appointment_id)
