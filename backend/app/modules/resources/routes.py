from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.permissions import require_ticket_manager
from app.database.session import get_db
from app.modules.resources import service
from app.modules.resources.repository import skill_facts
from app.modules.resources.schemas import RequirementUpdate, ResourceCreate, ResourceRead, ResourceUpdate, SkillUpdate
from app.shared.exceptions import not_found

router = APIRouter(prefix="/resources/institutes/{institute_id}", tags=["resources"])


def _reader(institute_id: str, user: dict = Depends(require_ticket_manager)):
    if user.get("institute_id") != institute_id:
        raise HTTPException(status_code=403, detail="Institut non autorise")
    return user


def _manager(user: dict = Depends(_reader)):
    if user["role"] != "responsable_institut":
        raise HTTPException(status_code=403, detail="Configuration reservee a la responsable de l'institut")
    return user


@router.get("", response_model=list[ResourceRead])
def get_resources(institute_id: str, user: dict = Depends(_reader), db: Session = Depends(get_db)):
    return service.list_resources(db, institute_id)


@router.post("", response_model=ResourceRead)
def post_resource(institute_id: str, payload: ResourceCreate, user: dict = Depends(_manager), db: Session = Depends(get_db)):
    return service.create_resource(db, institute_id, payload, user.get("sub"))


@router.patch("/{resource_id}", response_model=ResourceRead)
def patch_resource(institute_id: str, resource_id: str, payload: ResourceUpdate,
                   user: dict = Depends(_manager), db: Session = Depends(get_db)):
    return service.update_resource(db, institute_id, resource_id, payload, user.get("sub"))


@router.get("/employees/{employee_id}/skills", response_model=SkillUpdate)
def get_skills(institute_id: str, employee_id: str, user: dict = Depends(_reader), db: Session = Depends(get_db)):
    facts = skill_facts(db, institute_id)
    if employee_id not in facts:
        raise not_found("Collaboratrice introuvable")
    return {"skills": sorted(facts[employee_id])}


@router.patch("/employees/{employee_id}/skills", response_model=SkillUpdate)
def patch_skills(institute_id: str, employee_id: str, payload: SkillUpdate,
                 user: dict = Depends(_manager), db: Session = Depends(get_db)):
    return {"skills": service.update_employee_skills(db, institute_id, employee_id, payload, user.get("sub"))}


@router.get("/services/{service_id}/requirements", response_model=RequirementUpdate)
def get_requirements(institute_id: str, service_id: str, user: dict = Depends(_reader), db: Session = Depends(get_db)):
    return service.read_requirements(db, institute_id, service_id)


@router.patch("/services/{service_id}/requirements", response_model=RequirementUpdate)
def patch_requirements(institute_id: str, service_id: str, payload: RequirementUpdate,
                       user: dict = Depends(_manager), db: Session = Depends(get_db)):
    return service.update_requirements(db, institute_id, service_id, payload, user.get("sub"))
