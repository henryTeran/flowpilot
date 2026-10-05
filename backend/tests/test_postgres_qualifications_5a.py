from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.employees.models import Employee
from app.modules.resources.models import EmployeeSkill
from app.modules.resources.schemas import RequirementUpdate, SkillUpdate
from app.modules.resources.service import update_requirements, update_employee_skills
from app.modules.tickets.models import QueueTicket
from app.modules.tickets.service import assign_ticket
from test_postgres_scheduling_4d import postgres_flow, race, tickets


def test_skill_revocation_and_assignment_share_the_institute_lock(postgres_flow):
    engine, institute, employee, service = postgres_flow
    with Session(engine) as db:
        update_requirements(db, institute, service, RequirementUpdate(skills=["SPECIAL"]))
        update_employee_skills(db, institute, employee, SkillUpdate(skills=["SPECIAL"]))
    ticket = tickets(postgres_flow, 1)[0]
    def revoke(db):
        update_employee_skills(db, institute, employee, SkillUpdate(skills=[]))
        return db.get(Employee, employee)
    results = race(engine, [lambda db: assign_ticket(db, ticket, employee), revoke])
    assert sorted(status for status, _ in results) == ["conflict", "ok"]
    with Session(engine) as db:
        assigned = db.get(QueueTicket, ticket).status == "assigned"
        has_skill = db.scalar(select(EmployeeSkill.skill_code).where(
            EmployeeSkill.employee_id == employee, EmployeeSkill.skill_code == "SPECIAL")) is not None
        assert assigned == has_skill
