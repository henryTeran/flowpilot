from datetime import datetime
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, StringConstraints, AwareDatetime, field_validator
from sqlalchemy import select, or_, func
from app.modules.workforce.models import EmployeeRebooking as Original, RebookingCancellation as Cancellation
from app.modules.workforce.absence_schemas import AbsenceCancel, Reason, Key
from app.modules.workforce.rebooking_sources import ExecutionCapture, BookingCapture, execution, booking
from app.modules.workforce.certifications import signed_actor
from app.modules.workforce.objectives import require_employee
from app.modules.workforce.schemas import MatrixPage
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import business_error, not_found
from app.shared.ids import new_id
from app.shared.time import utcnow, explicit_utc_instant

Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class RebookingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_kind: Literal["session", "appointment"]
    source_id: Identifier
    target_appointment_id: Identifier
    reason: Reason
    idempotency_key: Key


class CancellationRead(AbsenceCancel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    institute_id: str
    rebooking_id: str
    actor_id: str
    created_at: AwareDatetime

    @field_validator("created_at", mode="before")
    @classmethod
    def aware(cls, v): return explicit_utc_instant(v) if isinstance(v, datetime) else v


class RebookingRead(RebookingCreate):
    id: str
    institute_id: str
    employee_id: str
    actor_id: str
    created_at: AwareDatetime
    source_capture: ExecutionCapture
    booking_capture: BookingCapture
    cancellation: CancellationRead | None = None


class RebookingPage(BaseModel):
    institute_id: str
    employee_id: str
    generated_at: AwareDatetime
    page: MatrixPage
    rows: list[RebookingRead]


def dto(row, cancellation=None):
    return RebookingRead(id=row.id, institute_id=row.institute_id, employee_id=row.employee_id, actor_id=row.actor_id,
        source_kind="session" if row.session_id else "appointment", source_id=row.session_id or row.source_appointment_id,
        target_appointment_id=row.target_appointment_id, reason=row.reason, idempotency_key=row.idempotency_key,
        created_at=explicit_utc_instant(row.created_at), source_capture=row.source_capture, booking_capture=row.booking_capture,
        cancellation=CancellationRead.model_validate(cancellation) if cancellation else None)


def snapshot(db, row):
    cancellation = db.scalar(select(Cancellation).where(Cancellation.institute_id == row.institute_id, Cancellation.rebooking_id == row.id))
    return dto(row, cancellation)


def require(db, institute, identifier):
    row = db.scalar(select(Original).where(Original.institute_id == institute, Original.id == identifier))
    if row is None: raise not_found("Rebooking introuvable")
    return row


def original(db, institute, key):
    row = db.scalar(select(Original).where(Original.institute_id == institute, Original.idempotency_key == key))
    return snapshot(db, row) if row else None


def create(db, institute, payload, actor):
    signed_actor(actor); lock_institute(db, institute)
    old = original(db, institute, payload.idempotency_key)
    if old:
        if old.actor_id != actor or old.model_dump(include=set(RebookingCreate.model_fields)) != payload.model_dump():
            raise business_error("La cle conserve les conditions et l'acteur originaux")
        return old
    now = utcnow()
    source = execution(db, institute, payload.source_kind, payload.source_id, now)
    target = booking(db, institute, payload.target_appointment_id, source, now)
    source_column = Original.session_id if source.kind == "session" else Original.source_appointment_id
    active = select(Original.id).outerjoin(Cancellation, (Cancellation.institute_id == Original.institute_id) & (Cancellation.rebooking_id == Original.id)) \
        .where(Original.institute_id == institute, Cancellation.id.is_(None),
            or_(source_column == source.id, Original.target_appointment_id == target.appointment_id)).limit(1)
    if db.scalar(active): raise business_error("Cette prestation ou reservation possede deja une attribution active")
    row = Original(id=new_id("rebook"), institute_id=institute, employee_id=source.employee_id,
        session_id=source.id if source.kind == "session" else None, source_appointment_id=source.id if source.kind == "appointment" else None,
        target_appointment_id=target.appointment_id, source_capture=source.model_dump(mode="json"), booking_capture=target.model_dump(mode="json"),
        reason=payload.reason, idempotency_key=payload.idempotency_key, actor_id=actor, created_at=now)
    db.add(row); db.commit(); db.refresh(row)
    return snapshot(db, row)


def cancel(db, institute, identifier, payload, actor):
    signed_actor(actor); lock_institute(db, institute)
    old = db.scalar(select(Cancellation).where(Cancellation.institute_id == institute, Cancellation.idempotency_key == payload.idempotency_key))
    if old:
        if (old.rebooking_id, old.reason, old.actor_id) != (identifier, payload.reason, actor):
            raise business_error("La cle conserve les conditions et l'acteur originaux")
        return CancellationRead.model_validate(old)
    require(db, institute, identifier)
    if db.scalar(select(Cancellation.id).where(Cancellation.institute_id == institute, Cancellation.rebooking_id == identifier)):
        raise business_error("Ce rebooking possede deja son annulation originale")
    row = Cancellation(id=new_id("rcancel"), institute_id=institute, rebooking_id=identifier, **payload.model_dump(), actor_id=actor, created_at=utcnow())
    db.add(row); db.commit(); db.refresh(row)
    return CancellationRead.model_validate(row)


def list_records(db, institute, employee, limit=20, offset=0):
    lock_institute(db, institute); require_employee(db, institute, employee)
    own = (Original.institute_id == institute, Original.employee_id == employee)
    total = db.scalar(select(func.count()).select_from(Original).where(*own))
    rows = db.execute(select(Original, Cancellation).outerjoin(Cancellation,
        (Cancellation.institute_id == Original.institute_id) & (Cancellation.rebooking_id == Original.id))
        .where(*own).order_by(Original.created_at.desc(), Original.id).offset(offset).limit(limit))
    return RebookingPage(institute_id=institute, employee_id=employee, generated_at=utcnow(),
        page=MatrixPage(offset=offset, limit=limit, total=total), rows=[dto(row, cancelled) for row, cancelled in rows])
