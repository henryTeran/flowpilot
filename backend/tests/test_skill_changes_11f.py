from sqlalchemy import select
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.resources.repository import skill_facts
from app.modules.workforce.models import EmployeeSkillChange
from test_workforce_absences_11b import setup
from test_ticket_workflow import _auth_headers
from test_postgres_scheduling_4d import postgres_flow
from app.modules.workforce.skill_changes import create, SkillChangeCreate
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from fastapi import HTTPException
import pytest
from test_resources_skills_5a import resource_flow, requirements, skills
from test_ticket_workflow import _create_ticket


def test_original_skill_change_recovery_does_not_reapply_after_later_change(client):
    institute, employee, _, base, headers = setup(client)
    with Session(main_module.engine) as db:
        before = sorted(skill_facts(db, institute, [employee])[employee])
    body = {"employee_id": employee, "expected_skills": before, "skills": [*before, "NEW_DECLARED"],
            "reason": "Manager configured", "idempotency_key": "first"}
    reply = client.post(base + "/skill-changes", headers=headers, json=body)
    assert reply.status_code == 200, reply.text
    original = reply.json()
    assert original["actor_id"] == "test-user"
    second = {**body, "expected_skills": original["skills"], "skills": before, "idempotency_key": "second"}
    assert client.post(base + "/skill-changes", headers=headers, json=second).status_code == 200
    assert client.post(base + "/skill-changes", headers=headers, json=body).json() == original
    assert client.get(base + "/skill-changes/original/first", headers=headers).json() == original
    assert client.get(base + "/skill-changes/original/missing", headers=headers).json() is None
    assert client.post(base + "/skill-changes", headers=headers, json={**body, "reason": "Changed"}).status_code == 400
    assert client.post(base + "/skill-changes", headers=headers, json={**second, "idempotency_key": "stale"}).status_code == 400
    with Session(main_module.engine) as db:
        assert sorted(skill_facts(db, institute, [employee])[employee]) == before
        assert len(list(db.scalars(select(EmployeeSkillChange)))) == 2


def test_skill_change_roles_scope_and_invalid_conditions(client):
    institute, employee, _, base, headers = setup(client)
    with Session(main_module.engine) as db:
        before = sorted(skill_facts(db, institute, [employee])[employee])
    body = {"employee_id": employee, "expected_skills": before, "skills": before,
            "reason": "Reviewed unchanged", "idempotency_key": "review"}
    for auth in [_auth_headers("accueil", institute), _auth_headers("responsable_institut", "foreign")]:
        assert client.post(base + "/skill-changes", headers=auth, json=body).status_code == 403
        assert client.get(base + "/skill-changes/original/review", headers=auth).status_code == 403
    assert client.post(base + "/skill-changes", headers=headers, json={**body, "employee_id": "foreign"}).status_code == 404
    for change in [{"expected_skills": ["DUP", "DUP"]}, {"skills": ["DUP", "DUP"]}, {"reason": " "}, {"actor_id": "forged"}]:
        assert client.post(base + "/skill-changes", headers=headers, json={**body, **change}).status_code == 422
    assert client.post(base + "/skill-changes", headers=headers, json=body).status_code == 200


def test_actual_postgres_skill_changes_serialize_competing_expected_states(postgres_flow, monkeypatch):
    engine, institute, employee, _ = postgres_flow
    with Session(engine) as db:
        before = sorted(skill_facts(db, institute, [employee])[employee])
    barrier = Barrier(2)
    def change(code):
        payload = SkillChangeCreate(employee_id=employee, expected_skills=before, skills=[*before, code],
                                   reason="Race fixture", idempotency_key=code)
        with Session(engine) as db:
            barrier.wait(timeout=10)
            try:
                return create(db, institute, payload, "signed").id
            except HTTPException as error:
                db.rollback()
                assert error.status_code == 400
                return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(change, code) for code in ("A", "B")]
        results = [future.result(timeout=20) for future in futures]
    assert sum(value is not None for value in results) == 1
    with Session(engine) as db:
        assert len(list(db.scalars(select(EmployeeSkillChange)))) == 1
        assert len(skill_facts(db, institute, [employee])[employee]-set(before)) == 1
        current = sorted(skill_facts(db, institute, [employee])[employee])
        original_id = db.scalar(select(EmployeeSkillChange.id))
        from app.modules.workforce import skill_changes
        from sqlalchemy.exc import IntegrityError
        from app.modules.resources.models import ResourceConfigurationEvent
        events = len(list(db.scalars(select(ResourceConfigurationEvent))))
        monkeypatch.setattr(skill_changes, "new_id", lambda _: original_id)
        with pytest.raises(IntegrityError):
            create(db, institute, SkillChangeCreate(employee_id=employee, expected_skills=current,
                   skills=[*current, "ROLLBACK"], reason="Atomic failure fixture", idempotency_key="rollback"), "signed")
        db.rollback()
        assert sorted(skill_facts(db, institute, [employee])[employee]) == current
        assert len(list(db.scalars(select(EmployeeSkillChange)))) == 1
        assert len(list(db.scalars(select(ResourceConfigurationEvent)))) == events


def test_original_skill_change_preserves_committed_service_protection(client, resource_flow):
    flow = resource_flow
    assert skills(client, flow, codes=["REQUIRED"]).status_code == 200
    assert requirements(client, flow, skills=["REQUIRED"]).status_code == 200
    ticket = _create_ticket(client, flow[0], flow[2][0]["id"])
    assert client.patch(f"/api/v1/tickets/{ticket['id']}/assign", headers=flow[4],
                        json={"employee_id": flow[1][0]["id"]}).status_code == 200
    body = {"employee_id": flow[1][0]["id"], "expected_skills": ["REQUIRED"], "skills": [],
            "reason": "Attempted removal", "idempotency_key": "protected"}
    base = f"/api/v1/workforce/institutes/{flow[0]}"
    assert client.post(base + "/skill-changes", headers=flow[3], json=body).status_code == 400
    assert client.get(base + "/skill-changes/original/protected", headers=flow[3]).json() is None
    with Session(main_module.engine) as db:
        assert skill_facts(db, flow[0], [body['employee_id']])[body['employee_id']] == {"REQUIRED"}
