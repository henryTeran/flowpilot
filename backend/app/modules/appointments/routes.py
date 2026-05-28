from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.modules.appointments.schemas import AppointmentCreate, AppointmentRead
from app.modules.appointments.service import cancel_appointment, create_appointment, list_today_appointments

router = APIRouter(prefix="/appointments", tags=["appointments"])


@router.get("", response_model=list[AppointmentRead])
def get_appointments(institute_id: str, db: Session = Depends(get_db)) -> list[AppointmentRead]:
    return list_today_appointments(db, institute_id)


@router.post("", response_model=AppointmentRead)
def post_appointment(payload: AppointmentCreate, db: Session = Depends(get_db)) -> AppointmentRead:
    return create_appointment(db, payload)


@router.patch("/{appointment_id}/cancel", response_model=AppointmentRead)
def patch_cancel_appointment(appointment_id: str, db: Session = Depends(get_db)) -> AppointmentRead:
    return cancel_appointment(db, appointment_id)
