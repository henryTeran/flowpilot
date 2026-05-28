from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.appointments.models import Appointment

ACTIVE_APPOINTMENT_STATUSES = ["scheduled", "confirmed", "arrived"]


def get_appointment(db: Session, appointment_id: str) -> Appointment | None:
    return db.get(Appointment, appointment_id)


def list_appointments_for_day(db: Session, institute_id: str, day: datetime) -> list[Appointment]:
    start = day.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)

    return list(
        db.scalars(
            select(Appointment)
            .where(
                Appointment.institute_id == institute_id,
                Appointment.start_time >= start,
                Appointment.start_time < end,
                Appointment.status != "cancelled",
            )
            .order_by(Appointment.start_time)
        ).all()
    )


def save_appointment(db: Session, appointment: Appointment) -> Appointment:
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    return appointment
