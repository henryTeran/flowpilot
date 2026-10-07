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
from app.modules.workforce.certification_schemas import CertificationCreate, CertificationRevoke, CertificationRead, RevocationRead, CertificationPage
from app.modules.workforce.skill_changes import SkillChangeCreate, SkillChangeRead
from app.modules.workforce.revenue import EmployeeRevenue
from app.modules.workforce.objective_schemas import ObjectiveCreate, ObjectiveCancel, ObjectiveRead, CancellationRead as ObjectiveCancellationRead, ObjectivePage
from app.modules.workforce.work_interval_schemas import WorkIntervalCreate, WorkIntervalRead, WorkIntervalCancellationRead, WorkIntervalPage
from app.modules.workforce.work_hours import EmployeeWorkHours

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
        raise HTTPException(status_code=403, detail="Gestion de l'equipe reservee a la responsable signee de cet institut")
    return user


@router.post("/skill-changes", response_model=SkillChangeRead)
def create_skill_change(institute_id: str, payload: SkillChangeCreate, user: dict = Depends(absence_manager), db: Session = Depends(get_db)):
    from app.modules.workforce.skill_changes import create
    return create(db, institute_id, payload, user["sub"])


@router.post("/work-intervals", response_model=WorkIntervalRead)
def create_work_interval(institute_id: str, payload: WorkIntervalCreate, user: dict = Depends(absence_manager), db: Session = Depends(get_db)):
    from app.modules.workforce.work_intervals import create
    return create(db, institute_id, payload, user["sub"])


@router.get("/employees/{employee_id}/work-hours", response_model=EmployeeWorkHours)
def employee_work_hours(institute_id: str, employee_id: str, day: date, limit: int = Query(20, ge=1, le=50),
                        offset: int = Query(0, ge=0, le=2147483647), user: dict = Depends(absence_manager), db: Session = Depends(get_db)):
    from app.modules.workforce.work_hours import read
    return read(db, institute_id, employee_id, day, limit, offset)


@router.get("/employees/{employee_id}/work-intervals", response_model=WorkIntervalPage)
def employee_work_intervals(institute_id: str, employee_id: str, limit: int = Query(20, ge=1, le=50),
                            offset: int = Query(0, ge=0, le=2147483647), user: dict = Depends(absence_manager), db: Session = Depends(get_db)):
    from app.modules.workforce.work_intervals import list_records
    return list_records(db, institute_id, employee_id, limit, offset)


@router.get("/work-intervals/original/{key}", response_model=WorkIntervalRead | None)
def original_work_interval(institute_id: str, key: str, user: dict = Depends(absence_manager), db: Session = Depends(get_db)):
    from sqlalchemy import select
    from app.modules.workforce.models import EmployeeWorkInterval
    from app.modules.workforce.work_intervals import snapshot
    row = db.scalar(select(EmployeeWorkInterval).where(EmployeeWorkInterval.institute_id == institute_id, EmployeeWorkInterval.idempotency_key == key))
    return snapshot(db, row) if row else None


@router.get("/work-interval-cancellations/original/{key}", response_model=WorkIntervalCancellationRead | None)
def original_work_interval_cancellation(institute_id: str, key: str, user: dict = Depends(absence_manager), db: Session = Depends(get_db)):
    from sqlalchemy import select
    from app.modules.workforce.models import WorkIntervalCancellation
    return db.scalar(select(WorkIntervalCancellation).where(WorkIntervalCancellation.institute_id == institute_id, WorkIntervalCancellation.idempotency_key == key))


@router.get("/work-intervals/{identifier}", response_model=WorkIntervalRead)
def read_work_interval(institute_id: str, identifier: str, user: dict = Depends(absence_manager), db: Session = Depends(get_db)):
    from app.modules.workforce.work_intervals import require, snapshot
    return snapshot(db, require(db, institute_id, identifier))


@router.post("/work-intervals/{identifier}/cancel", response_model=WorkIntervalCancellationRead)
def cancel_work_interval(institute_id: str, identifier: str, payload: AbsenceCancel, user: dict = Depends(absence_manager), db: Session = Depends(get_db)):
    from app.modules.workforce.work_intervals import cancel
    return cancel(db, institute_id, identifier, payload, user["sub"])


@router.post("/objectives", response_model=ObjectiveRead)
def create_objective(institute_id: str, payload: ObjectiveCreate, user: dict = Depends(absence_manager), db: Session = Depends(get_db)):
    from app.modules.workforce.objectives import create
    return create(db, institute_id, payload, user["sub"])


@router.get("/employees/{employee_id}/objectives", response_model=ObjectivePage)
def employee_objectives(institute_id: str, employee_id: str, limit: int = Query(20, ge=1, le=50),
                        offset: int = Query(0, ge=0, le=2147483647), user: dict = Depends(absence_manager), db: Session = Depends(get_db)):
    from app.modules.workforce.objectives import list_records
    return list_records(db, institute_id, employee_id, limit, offset)


@router.get("/objectives/original/{key}", response_model=ObjectiveRead | None)
def original_objective(institute_id: str, key: str, user: dict = Depends(absence_manager), db: Session = Depends(get_db)):
    from sqlalchemy import select
    from app.modules.workforce.models import EmployeeObjective
    from app.modules.workforce.objectives import snapshot
    row = db.scalar(select(EmployeeObjective).where(EmployeeObjective.institute_id == institute_id, EmployeeObjective.idempotency_key == key))
    return snapshot(db, row) if row else None


@router.get("/objective-cancellations/original/{key}", response_model=ObjectiveCancellationRead | None)
def original_objective_cancellation(institute_id: str, key: str, user: dict = Depends(absence_manager), db: Session = Depends(get_db)):
    from sqlalchemy import select
    from app.modules.workforce.models import ObjectiveCancellation
    return db.scalar(select(ObjectiveCancellation).where(ObjectiveCancellation.institute_id == institute_id, ObjectiveCancellation.idempotency_key == key))


@router.get("/objectives/{identifier}", response_model=ObjectiveRead)
def read_objective(institute_id: str, identifier: str, user: dict = Depends(absence_manager), db: Session = Depends(get_db)):
    from app.modules.workforce.objectives import require, snapshot
    return snapshot(db, require(db, institute_id, identifier))


@router.post("/objectives/{identifier}/cancel", response_model=ObjectiveCancellationRead)
def cancel_objective(institute_id: str, identifier: str, payload: ObjectiveCancel, user: dict = Depends(absence_manager), db: Session = Depends(get_db)):
    from app.modules.workforce.objectives import cancel
    return cancel(db, institute_id, identifier, payload, user["sub"])


@router.get("/employees/{employee_id}/revenue", response_model=EmployeeRevenue)
def employee_revenue(institute_id: str, employee_id: str, day: date,
                     limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0, le=2147483647),
                     user: dict = Depends(absence_manager), db: Session = Depends(get_db)):
    from app.modules.workforce.revenue import read
    return read(db, institute_id, employee_id, day, limit, offset)


@router.get("/skill-changes/original/{key}", response_model=SkillChangeRead | None)
def original_skill_change(institute_id: str, key: str, user: dict = Depends(absence_manager), db: Session = Depends(get_db)):
    from sqlalchemy import select
    from app.modules.workforce.models import EmployeeSkillChange
    return db.scalar(select(EmployeeSkillChange).where(EmployeeSkillChange.institute_id == institute_id,
                      EmployeeSkillChange.idempotency_key == key))


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


@router.post("/certifications", response_model=CertificationRead)
def create_certification(institute_id: str, payload: CertificationCreate, user: dict = Depends(absence_manager), db: Session = Depends(get_db)):
    from app.modules.workforce.certifications import create
    return create(db, institute_id, payload, user["sub"])


@router.get("/employees/{employee_id}/certifications", response_model=CertificationPage)
def list_certifications(institute_id: str, employee_id: str, limit: int = Query(50, ge=1, le=100),
                        offset: int = Query(0, ge=0, le=2147483647), user: dict = Depends(absence_manager), db: Session = Depends(get_db)):
    from app.modules.workforce.certifications import list_records
    return list_records(db, institute_id, employee_id, limit, offset)


@router.get("/certifications/original/{key}", response_model=CertificationRead | None)
def original_certification(institute_id: str, key: str, user: dict = Depends(absence_manager), db: Session = Depends(get_db)):
    from sqlalchemy import select
    from app.modules.workforce.models import EmployeeCertification
    from app.modules.workforce.certifications import snapshot
    row = db.scalar(select(EmployeeCertification).where(EmployeeCertification.institute_id == institute_id,
                                                  EmployeeCertification.idempotency_key == key))
    return snapshot(db, row) if row else None


@router.get("/certification-revocations/original/{key}", response_model=RevocationRead | None)
def original_revocation(institute_id: str, key: str, user: dict = Depends(absence_manager), db: Session = Depends(get_db)):
    from sqlalchemy import select
    from app.modules.workforce.models import CertificationRevocation
    return db.scalar(select(CertificationRevocation).where(CertificationRevocation.institute_id == institute_id,
                                              CertificationRevocation.idempotency_key == key))


@router.get("/certifications/{identifier}", response_model=CertificationRead)
def read_certification(institute_id: str, identifier: str, user: dict = Depends(absence_manager), db: Session = Depends(get_db)):
    from app.modules.workforce.certifications import require, snapshot
    return snapshot(db, require(db, institute_id, identifier))


@router.post("/certifications/{identifier}/revoke", response_model=RevocationRead)
def revoke_certification(institute_id: str, identifier: str, payload: CertificationRevoke,
                         user: dict = Depends(absence_manager), db: Session = Depends(get_db)):
    from app.modules.workforce.certifications import revoke
    return revoke(db, institute_id, identifier, payload, user["sub"])
