from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.permissions import require_same_institute, require_ticket_manager
from app.database.session import get_db
from app.modules.employees.repository import get_employee, list_by_institute
from app.modules.employees.schemas import EmployeeCreate, EmployeeRead, EmployeeStatusUpdate
from app.modules.employees.service import change_employee_status, create_employee
from app.shared.pagination import PaginationParams, pagination_params

router = APIRouter(prefix="/employees", tags=["employees"])


@router.get("", response_model=list[EmployeeRead])
def list_employees(
    institute_id: str,
    pagination: PaginationParams = Depends(pagination_params),
    current_user: dict[str, str | None] = Depends(require_ticket_manager),
    db: Session = Depends(get_db),
) -> list[EmployeeRead]:
    require_same_institute(current_user, institute_id)
    return list_by_institute(db, institute_id, limit=pagination.limit, offset=pagination.offset)


@router.post("", response_model=EmployeeRead)
def post_employee(
    payload: EmployeeCreate,
    current_user: dict[str, str | None] = Depends(require_ticket_manager),
    db: Session = Depends(get_db),
) -> EmployeeRead:
    require_same_institute(current_user, payload.institute_id)
    return create_employee(db, payload)


@router.patch("/{employee_id}/status", response_model=EmployeeRead)
def patch_employee_status(
    employee_id: str,
    payload: EmployeeStatusUpdate,
    current_user: dict[str, str | None] = Depends(require_ticket_manager),
    db: Session = Depends(get_db),
) -> EmployeeRead:
    employee = get_employee(db, employee_id)
    if employee:
        require_same_institute(current_user, employee.institute_id)
    try:
        return change_employee_status(db, employee_id, payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
