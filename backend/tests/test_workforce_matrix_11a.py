from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event

import pytest
from sqlalchemy import delete, event, select
from sqlalchemy.orm import Session

import app.main as main_module
from app.modules.employees.models import Employee
from app.modules.institutes.models import Institute
from app.modules.resources.models import EmployeeSkill, ServiceRequirement
from app.modules.resources.repository import qualifies_for_services, requirement_facts, skill_facts
from app.modules.resources.schemas import SkillUpdate
from app.modules.resources.service import update_employee_skills
from app.modules.services.models import Service
from app.modules.workforce.service import read_skill_matrix
from test_postgres_scheduling_4d import postgres_flow
from test_ticket_workflow import _auth_headers, _bootstrap_reference_data


def seed_facts(engine, institute):
    with Session(engine) as db:
        employees = list(db.scalars(select(Employee).where(Employee.institute_id == institute).order_by(Employee.id)))
        services = list(db.scalars(select(Service).where(Service.status == "active").order_by(Service.id)))
        first, second = employees[:2]
        first.skills = ["LEGACY"]
        second.skills = []
        second.status = "absent"
        db.execute(delete(EmployeeSkill).where(EmployeeSkill.employee_id.in_([first.id, second.id])))
        for code in ["LEGACY", "STRUCTURED"]:
            db.add(EmployeeSkill(institute_id=institute, employee_id=first.id, skill_code=code))
        db.execute(delete(ServiceRequirement).where(ServiceRequirement.institute_id == institute,
                                                    ServiceRequirement.service_id.in_([service.id for service in services])))
        for code in ["LEGACY", "STRUCTURED"]:
            db.add(ServiceRequirement(institute_id=institute, service_id=services[0].id, skill_code=code))
        db.commit()
        return first.id, second.id, services[0].id, services[1].id


def test_matrix_uses_the_matching_engines_union_and_exposes_missing_or_unconfigured_requirements(client):
    institute, _, _ = _bootstrap_reference_data(client)
    first, second, required_service, unconfigured_service = seed_facts(main_module.engine, institute)
    path = f"/api/v1/workforce/institutes/{institute}/skill-matrix?service_limit=25"
    response = client.get(path, headers=_auth_headers(institute_id=institute))
    assert response.status_code == 200, response.text
    matrix = response.json()
    assert matrix["institute_id"] == institute and matrix["generated_at"].endswith("Z")
    assert next(row for row in matrix["employees"] if row["id"] == first)["skills"] == ["LEGACY", "STRUCTURED"]
    cells = {(cell["employee_id"], cell["service_id"]): cell for cell in matrix["cells"]}
    assert cells[first, required_service]["meets_recorded_requirements"] is True
    assert cells[first, required_service]["missing_skills"] == []
    assert cells[second, required_service]["missing_skills"] == ["LEGACY", "STRUCTURED"]
    assert cells[second, required_service]["meets_recorded_requirements"] is False
    assert next(row for row in matrix["employees"] if row["id"] == second)["status"] == "absent"
    assert next(row for row in matrix["services"] if row["id"] == unconfigured_service)["requirement_state"] == "none_recorded"
    assert cells[second, unconfigured_service]["meets_recorded_requirements"] is True
    with Session(main_module.engine) as db:
        for cell in matrix["cells"]:
            assert cell["meets_recorded_requirements"] == qualifies_for_services(db, institute, cell["employee_id"], [cell["service_id"]])
        assert skill_facts(db, institute, [first]) == {first: {"LEGACY", "STRUCTURED"}}
        assert skill_facts(db, institute, []) == requirement_facts(db, institute, []) == {}


def test_matrix_authentication_scope_roles_and_pagination_boundaries(client):
    institute, _, _ = _bootstrap_reference_data(client)
    path = f"/api/v1/workforce/institutes/{institute}/skill-matrix"
    for role, tenant in [("accueil", None), ("responsable_institut", "foreign"), ("collaboratrice", institute), ("direction", institute)]:
        assert client.get(path, headers=_auth_headers(role, tenant)).status_code == 403
    assert client.get(path).status_code == 403
    for role in ["accueil", "responsable_institut"]:
        assert client.get(path, headers=_auth_headers(role, institute)).status_code == 200
    missing = client.get("/api/v1/workforce/institutes/missing/skill-matrix", headers=_auth_headers(institute_id="missing"))
    assert missing.status_code == 404
    for query in ["employee_limit=0", "employee_limit=26", "service_limit=26", "service_offset=-1", "employee_offset=2147483648"]:
        assert client.get(f"{path}?{query}", headers=_auth_headers(institute_id=institute)).status_code == 422
    assert client.post(path, headers=_auth_headers("responsable_institut", institute), json={}).status_code == 405


def test_matrix_pages_both_axes_without_foreign_rows_or_inactive_services_and_query_count_is_constant(client):
    institute, employees, services = _bootstrap_reference_data(client)
    with Session(main_module.engine) as db:
        origin = db.get(Institute, institute)
        db.add(Institute(id="matrix-foreign", region_id=origin.region_id, name="Foreign", city="Other"))
        db.flush()
        db.add(Employee(id="matrix-foreign-employee", institute_id="matrix-foreign", first_name="Foreign", skills=["FOREIGN"]))
        db.add(ServiceRequirement(institute_id="matrix-foreign", service_id=services[0]["id"], skill_code="FOREIGN"))
        for index in range(60):
            db.add(Employee(id=f"matrix-emp-{index:03}", institute_id=institute, first_name=f"Test {index}", skills=[]))
            db.add(Service(id=f"matrix-svc-{index:03}", category_id=services[0]["category_id"], name=f"Service {index}", duration_min=10, status="active"))
        db.add(Service(id="matrix-inactive", category_id=services[0]["category_id"], name="Inactive", duration_min=10, status="inactive"))
        db.commit()
    selects = []
    def record(_connection, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            selects.append(statement)
    event.listen(main_module.engine, "before_cursor_execute", record)
    try:
        with Session(main_module.engine) as db:
            matrix = read_skill_matrix(db, institute, employee_limit=25, service_limit=25)
        assert len(selects) == 8
        assert len(matrix["cells"]) == 625
        assert len(matrix["employees"]) == len(matrix["services"]) == 25
        assert matrix["employee_page"]["total"] == len(employees) + 60
        assert matrix["service_page"]["total"] == len(services) + 60
        seen_employees, seen_services = [], []
        for offset in [0, 25, 50, 75]:
            selects.clear()
            with Session(main_module.engine) as db:
                page = read_skill_matrix(db, institute, offset, 25, offset, 25)
            assert len(selects) <= 8
            seen_employees.extend(row["id"] for row in page["employees"])
            seen_services.extend(row["id"] for row in page["services"])
        assert len(set(seen_employees)) == len(seen_employees) == matrix["employee_page"]["total"]
        assert len(set(seen_services)) == len(seen_services) == matrix["service_page"]["total"]
        assert "matrix-inactive" not in seen_services
        assert "matrix-foreign-employee" not in seen_employees
        assert all("FOREIGN" not in service["required_skills"] for service in matrix["services"])
    finally:
        event.remove(main_module.engine, "before_cursor_execute", record)


def test_actual_postgres_matrix_read_serializes_against_skill_replacement(postgres_flow):
    engine, institute, _, _ = postgres_flow
    first, _, service, _ = seed_facts(engine, institute)
    entered, release, writer_entered = Event(), Event(), Event()
    def writer_lock_attempt(_connection, _cursor, statement, _parameters, _context, _executemany):
        if entered.is_set() and "FOR UPDATE" in statement:
            writer_entered.set()
    def pause_after_legacy(_connection, _cursor, statement, _parameters, _context, _executemany):
        if "FROM employees" in statement and "employees.id IN" in statement and not entered.is_set():
            entered.set()
            assert release.wait(10)
    event.listen(engine, "after_cursor_execute", pause_after_legacy)
    event.listen(engine, "before_cursor_execute", writer_lock_attempt)
    try:
        def read():
            with Session(engine) as db:
                return read_skill_matrix(db, institute, employee_limit=25, service_limit=25)
        def write():
            with Session(engine) as db:
                return update_employee_skills(db, institute, first, SkillUpdate(skills=[]), "test-manager")
        with ThreadPoolExecutor(max_workers=2) as pool:
            reader = pool.submit(read)
            assert entered.wait(10)
            writer = pool.submit(write)
            assert writer_entered.wait(10)
            with pytest.raises(TimeoutError):
                writer.result(timeout=0.15)
            release.set()
            snapshot = reader.result(timeout=15)
            assert writer.result(timeout=15) == []
        original = next(cell for cell in snapshot["cells"] if cell["employee_id"] == first and cell["service_id"] == service)
        assert original["meets_recorded_requirements"] is True
        with Session(engine) as db:
            current = read_skill_matrix(db, institute, employee_limit=25, service_limit=25)
        updated = next(cell for cell in current["cells"] if cell["employee_id"] == first and cell["service_id"] == service)
        assert updated["meets_recorded_requirements"] is False and updated["missing_skills"] == ["LEGACY", "STRUCTURED"]
    finally:
        release.set()
        event.remove(engine, "after_cursor_execute", pause_after_legacy)
        event.remove(engine, "before_cursor_execute", writer_lock_attempt)
