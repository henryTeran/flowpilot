from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import date
from sqlalchemy.orm import Session

from app.core.permissions import require_ticket_manager
from app.database.session import get_db
from app.modules.workforce.schemas import SkillMatrixRead
from app.modules.workforce.service import read_skill_matrix
from app.modules.workforce import absences
from app.modules.workforce.absence_schemas import AbsenceCreate, AbsenceCancel, AbsenceRead, CancellationRead
from app.modules.workforce.calendar_schemas import EmployeeDayRead

router = APIRouter(prefix="/workforce/institutes/{institute_id}", tags=["workforce"])


@router.get("/skill-matrix", response_model=SkillMatrixRead)
def get_skill_matrix(
    institute_id: str,
    employee_offset: int = Query(0, ge=0, le=2147483647),
    employee_limit: int = Query(10, ge=1, le=25),
    service_offset: int = Query(0, ge=0, le=2147483647),
    service_limit: int = Query(10, ge=1, le=25),
    user: dict = Depends(require_ticket_manager),
    db: Session = Depends(get_db),
):
    if user.get("institute_id") != institute_id:
        raise HTTPException(status_code=403, detail="Institut non autorise")
    return read_skill_matrix(db, institute_id, employee_offset, employee_limit, service_offset, service_limit)


def absence_manager(institute_id: str, user: dict = Depends(require_ticket_manager)):
    if user.get("institute_id") != institute_id or user.get("role") != "responsable_institut" or not str(user.get("sub") or "").strip():
        raise HTTPException(status_code=403, detail="Absences reservees a la responsable signee de cet institut")
    return user


@router.post("/absences", response_model=AbsenceRead)
def create_absence(institute_id: str, payload: AbsenceCreate, user: dict = Depends(absence_manager), db: Session = Depends(get_db)):
    return absences.create(db, institute_id, payload, user["sub"])


@router.get("/absences", response_model=list[AbsenceRead])
def list_absences(institute_id: str, employee_id: str | None = None, limit: int = Query(50, ge=1, le=100),
                  offset: int = Query(0, ge=0, le=2147483647), user: dict = Depends(absence_manager), db: Session = Depends(get_db)):
    return absences.list_records(db, institute_id, employee_id, limit, offset)


@router.get("/absences/original/{key}", response_model=AbsenceRead | None)
def original_absence(institute_id: str, key: str, user: dict = Depends(absence_manager), db: Session = Depends(get_db)):
    from sqlalchemy import select
    from app.modules.workforce.models import EmployeeAbsence
    row = db.scalar(select(EmployeeAbsence).where(EmployeeAbsence.institute_id == institute_id, EmployeeAbsence.idempotency_key == key))
    return absences.snapshot(db, row) if row else None


@router.get("/absence-cancellations/original/{key}", response_model=CancellationRead | None)
def original_cancellation(institute_id: str, key: str, user: dict = Depends(absence_manager), db: Session = Depends(get_db)):
    from sqlalchemy import select
    from app.modules.workforce.models import AbsenceCancellation
    return db.scalar(select(AbsenceCancellation).where(AbsenceCancellation.institute_id == institute_id, AbsenceCancellation.idempotency_key == key))


@router.get("/absences/{identifier}", response_model=AbsenceRead)
def read_absence(institute_id: str, identifier: str, user: dict = Depends(absence_manager), db: Session = Depends(get_db)):
    return absences.snapshot(db, absences.require(db, institute_id, identifier))


@router.post("/absences/{identifier}/cancel", response_model=CancellationRead)
def cancel_absence(institute_id: str, identifier: str, payload: AbsenceCancel, user: dict = Depends(absence_manager), db: Session = Depends(get_db)):
    return absences.cancel(db, institute_id, identifier, payload, user["sub"])


@router.get("/employees/{employee_id}/day", response_model=EmployeeDayRead)
def employee_day(institute_id: str, employee_id: str, day: date,
                 limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0, le=2147483647),
                 user: dict = Depends(absence_manager), db: Session = Depends(get_db)):
    from app.modules.workforce.calendar import read_employee_day
    return read_employee_day(db, institute_id, employee_id, day, limit, offset)
