from datetime import timedelta

import pytest
from sqlalchemy.orm import Session

import app.main as main_module
from app.modules.employees.models import Employee
from app.modules.resources.models import EmployeeSkill, ResourceConfigurationEvent
from app.modules.scheduling.waiting_domain import EmployeeTimeline, QueueWork, project_queue
from app.shared.time import utcnow
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data, _create_ticket


@pytest.fixture
def resource_flow(client):
    institute, employees, services = _bootstrap_reference_data(client)
    manager = _auth_headers("responsable_institut", institute)
    operator = _auth_headers(institute_id=institute)
    prefix = f"/api/v1/resources/institutes/{institute}"
    return institute, employees, services, manager, operator, prefix


def requirements(client, flow, service_index=0, skills=None, resources=None):
    return client.patch(f"{flow[5]}/services/{flow[2][service_index]['id']}/requirements", headers=flow[3],
                        json={"skills": skills or [], "resources": resources or []})


def skills(client, flow, employee_index=0, codes=None):
    return client.patch(f"{flow[5]}/employees/{flow[1][employee_index]['id']}/skills", headers=flow[3],
                        json={"skills": codes or []})


@pytest.mark.parametrize("kind", ["room", "equipment", "bed", "chair", "device"])
def test_resource_types_creation_replay_and_configuration_audit(client, resource_flow, kind):
    flow = resource_flow
    payload = {"name": f"Test {kind}", "kind": kind, "capabilities": ["SPECIAL"]}
    first = client.post(flow[5], headers=flow[3], json=payload)
    retry = client.post(flow[5], headers=flow[3], json=payload)
    assert first.status_code == retry.status_code == 200
    assert first.json() == retry.json()
    listed = client.get(flow[5], headers=flow[4])
    assert len(listed.json()) == 1
    assert listed.json()[0]["institute_id"] == flow[0]
    path = f"{flow[5]}/{first.json()['id']}"
    assert client.patch(path, headers=flow[3], json={"status": "maintenance"}).status_code == 200
    assert client.patch(path, headers=flow[3], json={"status": "maintenance"}).status_code == 200
    with Session(main_module.engine) as db:
        assert db.query(ResourceConfigurationEvent).count() == 2
        assert all(event.actor_id == "test-user" for event in db.query(ResourceConfigurationEvent).all())


def test_resource_configuration_is_manager_only_and_strictly_tenant_scoped(client, resource_flow):
    flow = resource_flow
    body = {"name": "Room", "kind": "room"}
    assert client.post(flow[5], headers=flow[4], json=body).status_code == 403
    assert client.get(flow[5]).status_code == 403
    assert client.get(flow[5], headers=_auth_headers("collaboratrice", flow[0])).status_code == 403
    assert client.get(flow[5], headers=_auth_headers(institute_id=None)).status_code == 403
    assert client.get(flow[5], headers=_auth_headers(institute_id="other")).status_code == 403
    resource = client.post(flow[5], headers=flow[3], json=body).json()
    assert client.patch(f"{flow[5]}/foreign-id", headers=flow[3], json={"status": "inactive"}).status_code == 404
    foreign = "/api/v1/resources/institutes/other"
    assert client.get(foreign, headers=_auth_headers(institute_id="other")).json() == []
    assert client.patch(f"{foreign}/{resource['id']}", headers=_auth_headers("responsable_institut", "other"),
                        json={"status": "inactive"}).status_code == 404  # institute itself is missing
    assert client.get(f"{foreign}/employees/{flow[1][0]['id']}/skills", headers=_auth_headers(institute_id="other")).status_code == 404


@pytest.mark.parametrize("payload", [{"name": " ", "kind": "room"}, {"name": "Room", "kind": "invalid"},
                                     {"name": "Room", "kind": "room", "status": "broken"}])
def test_resource_inputs_are_validated(client, resource_flow, payload):
    assert client.post(resource_flow[5], headers=resource_flow[3], json=payload).status_code == 422


def test_requirements_and_skills_are_explicit_idempotent_and_mirrored(client, resource_flow):
    flow = resource_flow
    needs = [{"kind": "device", "capability": "LASER", "quantity": 1}]
    configured = requirements(client, flow, skills=["SPECIAL"], resources=needs)
    assert configured.status_code == 200, configured.text
    assert configured.json() == {"skills": ["SPECIAL"], "resources": needs}
    assert requirements(client, flow, skills=["SPECIAL"], resources=needs).status_code == 200
    assert skills(client, flow, codes=["SPECIAL"]).status_code == 200
    assert skills(client, flow, codes=["SPECIAL"]).status_code == 200
    with Session(main_module.engine) as db:
        employee_id = flow[1][0]["id"]
        assert db.get(Employee, employee_id).skills == ["SPECIAL"]
        assert [skill.skill_code for skill in db.query(EmployeeSkill).filter_by(employee_id=employee_id).all()] == ["SPECIAL"]
        assert db.query(ResourceConfigurationEvent).count() == 2
    path = f"{flow[5]}/employees/{flow[1][0]['id']}/skills"
    assert client.patch(path, headers=flow[4], json={"skills": ["ADMIN"]}).status_code == 403
    assert client.post("/api/v1/employees", headers=flow[4], json={"institute_id": flow[0], "first_name": "New",
                        "skills": ["SPECIAL"]}).status_code == 403


def test_skill_matching_blocks_assignment_direct_start_and_updates_wait_estimates(client, resource_flow):
    flow = resource_flow
    assert requirements(client, flow, skills=["SPECIAL"]).status_code == 200
    ticket = _create_ticket(client, flow[0], flow[2][0]["id"])
    assert ticket["estimated_start_time"] is None
    options_path = f"/api/v1/availability/{ticket['id']}/assignment-options?institute_id={flow[0]}"
    options = client.get(options_path, headers=flow[4]).json()["options"]
    assert all(not option["assignable"] and option["reason"] == "skills_missing" for option in options)
    assert client.patch(f"/api/v1/tickets/{ticket['id']}/assign", headers=flow[4],
                        json={"employee_id": flow[1][0]["id"]}).status_code == 400
    start = {"ticket_id": ticket["id"], "employee_id": flow[1][0]["id"], "service_id": flow[2][0]["id"]}
    assert client.post("/api/v1/planning/sessions/start", headers=flow[4], json=start).status_code == 400
    assert skills(client, flow, codes=["SPECIAL"]).status_code == 200
    refreshed = client.get(f"/api/v1/tickets/waiting?institute_id={flow[0]}", headers=flow[4]).json()
    assert refreshed[0]["estimated_start_time"] is not None
    assert client.post("/api/v1/planning/sessions/start", headers=flow[4], json=start).status_code == 200
    assert skills(client, flow, codes=[]).status_code == 400
    assert requirements(client, flow, skills=["DIFFERENT"]).status_code == 400
    assert requirements(client, flow, skills=["SPECIAL"]).status_code == 200


def test_multi_service_ticket_requires_all_skills_and_preserves_assignment_commitment(client, resource_flow):
    flow = resource_flow
    assert requirements(client, flow, 0, ["FIRST"]).status_code == 200
    assert requirements(client, flow, 1, ["SECOND"]).status_code == 200
    assert skills(client, flow, codes=["FIRST"]).status_code == 200
    created = client.post("/api/v1/tickets", headers=flow[4], json={"institute_id": flow[0],
                         "service_ids": [flow[2][0]["id"], flow[2][1]["id"]]})
    assert created.status_code == 200
    ticket = created.json()
    path = f"/api/v1/tickets/{ticket['id']}/assign"
    body = {"employee_id": flow[1][0]["id"]}
    assert client.patch(path, headers=flow[4], json=body).status_code == 400
    assert skills(client, flow, codes=["FIRST", "SECOND"]).status_code == 200
    assert client.patch(path, headers=flow[4], json=body).status_code == 200
    assert skills(client, flow, codes=["FIRST"]).status_code == 400


def test_booking_and_service_availability_require_qualifications(client, resource_flow):
    flow = resource_flow
    assert requirements(client, flow, skills=["SPECIAL"]).status_code == 200
    body = {"institute_id": flow[0], "service_id": flow[2][0]["id"], "employee_id": flow[1][0]["id"],
            "customer_name": "Test", "start_time": (utcnow() + timedelta(minutes=1)).isoformat()}
    assert client.post("/api/v1/appointments", headers=flow[4], json=body).status_code == 400
    path = f"/api/v1/availability/employees/{flow[1][0]['id']}?institute_id={flow[0]}&service_id={flow[2][0]['id']}"
    result = client.get(path, headers=flow[4]).json()
    assert not result["available"] and result["current_slot"]["reason"] == "skills_missing"
    assert skills(client, flow, codes=["SPECIAL"]).status_code == 200
    booked = client.post("/api/v1/appointments", headers=flow[4], json=body)
    assert booked.status_code == 200, booked.text
    assert skills(client, flow, codes=[]).status_code == 400


def test_requirements_validate_duplicates_and_quantity(client, resource_flow):
    flow = resource_flow
    path = f"{flow[5]}/services/{flow[2][0]['id']}/requirements"
    assert client.patch(path, headers=flow[3], json={"skills": ["S", "S"]}).status_code == 422
    assert client.patch(path, headers=flow[3], json={"skills": [], "resources": [{"kind": "room", "quantity": 0}]}).status_code == 422
    assert client.patch(path, headers=flow[3], json={"skills": [], "resources": [{"kind": "room"}, {"kind": "room"}]}).status_code == 422


def test_wait_projection_cannot_use_unqualified_parallel_employee():
    now = utcnow()
    result = project_queue([EmployeeTimeline("unqualified", now),
                            EmployeeTimeline("qualified", now + timedelta(minutes=20), skills=frozenset({"S"}))],
                           [QueueWork("ticket", 30, required_skills=frozenset({"S"}))])
    assert result["ticket"].employee_id == "qualified"
    assert result["ticket"].estimated_start_time == now + timedelta(minutes=20)


def test_skill_replacement_reconciles_stale_normalized_rows(client, resource_flow):
    flow = resource_flow
    employee_id = flow[1][0]["id"]
    with Session(main_module.engine) as db:
        legacy = list(db.get(Employee, employee_id).skills)
        db.add(EmployeeSkill(institute_id=flow[0], employee_id=employee_id, skill_code="STALE"))
        db.commit()
    assert skills(client, flow, codes=legacy).status_code == 200
    read = client.get(f"{flow[5]}/employees/{employee_id}/skills", headers=flow[4])
    assert "STALE" not in read.json()["skills"]


def test_manager_employee_creation_records_canonical_skills_and_actor(client, resource_flow):
    flow = resource_flow
    response = client.post("/api/v1/employees", headers=flow[3], json={"institute_id": flow[0],
                           "first_name": "New", "skills": ["SPECIAL"]})
    assert response.status_code == 200, response.text
    with Session(main_module.engine) as db:
        employee_id = response.json()["id"]
        assert db.query(EmployeeSkill).filter_by(employee_id=employee_id).one().skill_code == "SPECIAL"
        assert db.query(ResourceConfigurationEvent).filter_by(target_id=employee_id).one().actor_id == "test-user"


def test_resource_demand_without_proven_capacity_blocks_writes_and_estimates(client, resource_flow):
    flow = resource_flow
    assert requirements(client, flow, resources=[{"kind": "device", "capability": "LASER"}]).status_code == 200
    ticket = _create_ticket(client, flow[0], flow[2][0]["id"])
    assert ticket["estimated_start_time"] is None
    options = client.get(f"/api/v1/availability/{ticket['id']}/assignment-options?institute_id={flow[0]}", headers=flow[4]).json()["options"]
    assert all(not option["assignable"] for option in options)
    assert client.patch(f"/api/v1/tickets/{ticket['id']}/assign", headers=flow[4],
                        json={"employee_id": flow[1][0]["id"]}).status_code == 400
    assert client.post("/api/v1/planning/sessions/start", headers=flow[4], json={"ticket_id": ticket["id"],
                        "employee_id": flow[1][0]["id"], "service_id": flow[2][0]["id"]}).status_code == 400
    assert client.post("/api/v1/appointments", headers=flow[4], json={"institute_id": flow[0],
                        "employee_id": flow[1][0]["id"], "service_id": flow[2][0]["id"], "customer_name": "Test",
                        "start_time": (utcnow() + timedelta(minutes=1)).isoformat()}).status_code == 400
