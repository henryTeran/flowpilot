from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.appointments.models import Appointment
from app.modules.institutes.calendar import day_bounds

ACTIVE_APPOINTMENT_STATUSES = ["scheduled", "confirmed", "arrived", "in_progress"]
FINAL_APPOINTMENT_STATUSES = ["completed", "cancelled", "no_show"]
ALL_APPOINTMENT_STATUSES = ACTIVE_APPOINTMENT_STATUSES + FINAL_APPOINTMENT_STATUSES


def get_appointment(db: Session, appointment_id: str) -> Appointment | None:
    return db.get(Appointment, appointment_id)


def list_appointments_for_day(db: Session, institute_id: str, day: date | datetime) -> list[Appointment]:
    start, end = day_bounds(db, institute_id, day)

    # On retourne aussi les RDV terminés / absents / annulés afin que l’agenda puisse
    # les afficher dans une section historique séparée, sans les mélanger aux actifs.
    return list(
        db.scalars(
            select(Appointment)
            .where(
                Appointment.institute_id == institute_id,
                Appointment.start_time >= start,
                Appointment.start_time < end,
            )
            .order_by(Appointment.start_time)
        ).all()
    )


def save_appointment(db: Session, appointment: Appointment) -> Appointment:
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    return appointment
