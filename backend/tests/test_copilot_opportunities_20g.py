from datetime import datetime, timedelta
from sqlalchemy import event, select
from sqlalchemy.orm import Session
import app.main as main_module
from app.database.session import get_db
from app.modules.copilot import query
from app.modules.employees.models import Employee
from app.modules.services.models import Service
from app.modules.resources.models import ServiceRequirement
from app.modules.tickets.models import QueueTicket, TicketLine
from app.modules.appointments.models import Appointment
from app.modules.waitlist.originals import fingerprint
from test_revenue_billing_14a import NOW
from test_postgres_scheduling_4d import postgres_flow
from test_ticket_workflow import _bootstrap_reference_data, _auth_headers


def exercise(client, engine, institute, employee, service, monkeypatch):
    monkeypatch.setattr(query.slot_opportunities, "utcnow", lambda: NOW)
    with Session(engine) as db:
        for row in db.scalars(select(Employee).where(Employee.institute_id == institute)):
            row.status = "unavailable"
        db.get(Employee, employee).status = "available"
        db.get(Employee, employee).skills = ["copilot-commercial"]
        selected = db.get(Service, service)
        selected.duration_min = 20
        selected.requires_machine = False
        db.add(ServiceRequirement(institute_id=institute, service_id=service, skill_code="copilot-commercial"))
        db.commit()
    ui = {"service_id": service, "horizon_end": (NOW+timedelta(hours=2)).isoformat()}
    def post(selection=ui, role="responsable_institut"):
        return client.post("/api/v1/copilot/query", headers=_auth_headers(role, institute),
            json={"message": "Examiner les opportunites de revenus", "ui_context": selection})
    statements = []
    def collect(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lstrip().split()[0].upper())
    event.listen(engine, "before_cursor_execute", collect)
    try:
        response = post()
        assert response.status_code == 200, response.text
        value = response.json()
        evidence = value["evidence"]
        opportunity = evidence["result"]["opportunity"]
        assert value["capability"] == "REVENUE_OPPORTUNITIES" and value["actions"] == []
        assert opportunity["evidence"]["employee_id"] == employee
        assert opportunity["estimated_value"] is None and not opportunity["capacity_reserved"] and not opportunity["action_executed"]
        assert evidence["fingerprint"] == fingerprint({k: v for k, v in evidence.items() if k != "fingerprint"})
        assert '"customer_id"' not in response.text and '"employee_name"' not in response.text
    finally:
        event.remove(engine, "before_cursor_execute", collect)
    assert not set(statements) & {"INSERT", "UPDATE", "DELETE", "ALTER", "CREATE", "DROP"}
    with Session(engine) as db:
        db.add(QueueTicket(id="opportunity_prior", institute_id=institute, ticket_number="P", status="waiting", arrival_time=NOW))
        db.flush()
        db.add(TicketLine(id="opportunity_line", ticket_id="opportunity_prior", service_id=service, quantity=1, duration_minutes=20))
        db.add(Appointment(id="opportunity_blocker", institute_id=institute, employee_id=employee, service_id=service,
            customer_name="Private", start_time=NOW+timedelta(minutes=25), end_time=NOW+timedelta(minutes=60), status="confirmed"))
        db.commit()
    projected = post().json()["evidence"]["result"]["opportunity"]["evidence"]
    assert projected["prior_queue_count"] == 1
    assert datetime.fromisoformat(projected["projected_start"]) == NOW+timedelta(minutes=60)
    assert post({**ui, "horizon_end": (NOW+timedelta(minutes=60)).isoformat()}).json()["evidence"]["result"]["unavailable_reason"] == "outside_horizon"
    assert post(role="accueil").status_code == 403
    assert post({}).json()["status"] == "clarification"
    assert post({**ui, "horizon_end": 1}).status_code == 422
    assert post({**ui, "horizon_end": NOW.isoformat()}).status_code == 400
    assert post({**ui, "service_id": "missing"}).status_code == 404
    assert post({**ui, "customer_id": "injected"}).status_code == 400


def test_sqlite_opportunity_projection(client, monkeypatch):
    institute, employees, services = _bootstrap_reference_data(client)
    exercise(client, main_module.engine, institute, employees[0]["id"], services[0]["id"], monkeypatch)


def test_postgres_opportunity_projection(client, postgres_flow, monkeypatch):
    engine, institute, employee, service = postgres_flow
    def database():
        with Session(engine) as db:
            yield db
    main_module.app.dependency_overrides[get_db] = database
    monkeypatch.setattr(main_module, "engine", engine)
    exercise(client, engine, institute, employee, service, monkeypatch)
