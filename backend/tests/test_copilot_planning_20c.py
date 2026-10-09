from datetime import datetime, timedelta
from sqlalchemy import event
from sqlalchemy.orm import Session
import app.main as main_module
from app.database.session import get_db
from app.modules.copilot import query
from app.modules.appointments.models import Appointment
from app.modules.employees.models import Employee
from app.modules.institutes.models import Institute
from app.modules.waitlist.originals import fingerprint
from app.shared.time import utcnow
from test_postgres_scheduling_4d import postgres_flow
from test_ticket_workflow import _bootstrap_reference_data, _auth_headers


def exercise(client, engine, institute, employee, service, monkeypatch):
    now = utcnow()
    monkeypatch.setattr(query, "utcnow", lambda: now)
    monkeypatch.setattr(query.planning.planning, "utcnow", lambda: now)
    monkeypatch.setattr(query.capacity, "utcnow", lambda: now)
    with Session(engine) as db:
        db.get(Employee, employee).status = "available"
        db.add(Appointment(id="copilot_blocker", institute_id=institute, employee_id=employee, service_id=service,
            customer_name="Private client", phone="Secret phone", status="confirmed", start_time=now+timedelta(hours=1),
            end_time=now+timedelta(hours=2)))
        owner = db.get(Institute, institute)
        db.add(Institute(id="planning_foreign", region_id=owner.region_id, name="Other", city="Other"))
        db.flush()
        db.add(Employee(id="foreign_employee", institute_id="planning_foreign", first_name="Private foreign", status="available", skills=[]))
        db.commit()
    def post(message, ui=None, role="accueil", owner=institute):
        return client.post("/api/v1/copilot/query", headers=_auth_headers(role, owner),
            json={"message": message, "ui_context": ui or {}})
    messages = [("Consulter le planning du jour", {}, "PLANNING_READ", "accueil"),
        ("Consulter les creneaux libres du planning", {}, "PLANNING_GAPS", "accueil"),
        ("Mesurer la capacite enregistree des collaboratrices", {"day": (now-timedelta(days=1)).date().isoformat()}, "EMPLOYEE_CAPACITY", "responsable_institut")]
    statements = []
    def collect(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lstrip().split()[0].upper())
    event.listen(engine, "before_cursor_execute", collect)
    try:
        for message, ui, name, role in messages:
            response = post(message, ui, role)
            assert response.status_code == 200, response.text
            value = response.json()
            assert value["status"] == "answered" and value["capability"] == name and value["actions"] == []
            evidence = value["evidence"]
            assert evidence["fingerprint"] == fingerprint({k: v for k, v in evidence.items() if k != "fingerprint"})
            assert evidence["institute_id"] == institute
            assert all(secret not in response.text for secret in ("Private client", "Secret phone", "Private foreign", "foreign_employee", '"employee_name"'))
            result = evidence["result"]
            if name == "PLANNING_GAPS":
                row = next(row for row in result["rows"] if row["employee_id"] == employee)
                assert datetime.fromisoformat(row["current_slot"]["available_until"]) == now+timedelta(hours=1)
                assert row["upcoming_slots"][0]["blocking_appointment_id"] == "copilot_blocker"
                assert not result["booking_authorized"] and not result["complete_work_hours"]
            if name == "EMPLOYEE_CAPACITY":
                assert result["employee_count"] > 0 and result["employees_without_usable_hours"] > 0
                assert result["recorded_unoccupied_duration_us"] is None and result["bookable_capacity"] is None
    finally:
        event.remove(engine, "before_cursor_execute", collect)
    assert not set(statements) & {"INSERT", "UPDATE", "DELETE", "ALTER", "CREATE", "DROP"}
    assert post(messages[2][0], messages[2][1]).status_code == 403
    assert post(messages[2][0], role="responsable_institut").json()["status"] == "clarification"
    assert post(messages[2][0], {"day": 1780000000}, "responsable_institut").status_code == 422
    assert post(messages[2][0], {"day": (now+timedelta(days=1)).date().isoformat()}, "responsable_institut").status_code == 400
    assert post(messages[0][0], {"customer_id": "selected"}).status_code == 400
    assert post(messages[1][0], {"service_id": "absent"}).status_code == 404
    assert post(messages[0][0], owner="missing-institute").status_code == 404
    assert post(messages[0][0], role="collaboratrice").status_code == 403


def test_sqlite_actual_planning_services(client, monkeypatch):
    institute, employees, services = _bootstrap_reference_data(client)
    exercise(client, main_module.engine, institute, employees[0]["id"], services[0]["id"], monkeypatch)


def test_postgres_actual_planning_services(client, postgres_flow, monkeypatch):
    engine, institute, employee, service = postgres_flow
    def database():
        with Session(engine) as db:
            yield db
    main_module.app.dependency_overrides[get_db] = database
    monkeypatch.setattr(main_module, "engine", engine)
    exercise(client, engine, institute, employee, service, monkeypatch)
