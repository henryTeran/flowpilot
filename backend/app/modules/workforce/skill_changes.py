from datetime import datetime
from typing import Annotated
from pydantic import AwareDatetime, ConfigDict, Field, StringConstraints, field_validator, model_validator
from sqlalchemy import select
from app.modules.resources.schemas import SkillUpdate, Code
from app.modules.resources.repository import skill_facts
from app.modules.resources.service import update_employee_skills
from app.modules.workforce.absence_schemas import Reason, Key
from app.modules.workforce.models import EmployeeSkillChange
from app.modules.workforce.certifications import signed_actor
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import business_error, not_found
from app.shared.ids import new_id
from app.shared.time import explicit_utc_instant, utcnow


class SkillChangeCreate(SkillUpdate):
    employee_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    expected_skills: list[Code] = Field(max_length=100)
    reason: Reason
    idempotency_key: Key

    @model_validator(mode="after")
    def canonical(self):
        if len(set(self.expected_skills)) != len(self.expected_skills):
            raise ValueError("Chaque competence attendue doit etre unique")
        self.skills = sorted(self.skills)
        self.expected_skills = sorted(self.expected_skills)
        return self


class SkillChangeRead(SkillChangeCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    institute_id: str
    actor_id: str
    created_at: AwareDatetime

    @field_validator("created_at", mode="before")
    @classmethod
    def aware(cls, value):
        return explicit_utc_instant(value) if isinstance(value, datetime) else value


def create(db, institute, payload, actor):
    signed_actor(actor)
    lock_institute(db, institute)
    original = db.scalar(select(EmployeeSkillChange).where(EmployeeSkillChange.institute_id == institute,
                      EmployeeSkillChange.idempotency_key == payload.idempotency_key))
    if original:
        conditions = SkillChangeRead.model_validate(original).model_dump(include=set(type(payload).model_fields))
        if original.actor_id != actor or conditions != payload.model_dump():
            raise business_error("La cle conserve les conditions et l'acteur originaux")
        return original
    current = skill_facts(db, institute, [payload.employee_id]).get(payload.employee_id)
    if current is None:
        raise not_found("Collaboratrice introuvable")
    if sorted(current) != payload.expected_skills:
        raise business_error("Les competences ont change ; relisez avant de modifier")
    # Keep the existing commitment protection, legacy/structured sync and audit
    # in the same transaction as the exact original recovery fact.
    update_employee_skills(db, institute, payload.employee_id, SkillUpdate(skills=payload.skills), actor, commit=False)
    original = EmployeeSkillChange(id=new_id("esc"), institute_id=institute,
        **payload.model_dump(), actor_id=actor, created_at=utcnow())
    db.add(original)
    db.commit()
    db.refresh(original)
    return original
