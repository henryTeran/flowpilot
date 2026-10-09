from datetime import datetime, timedelta, timezone
from sqlalchemy import event
from sqlalchemy.orm import Session
import app.main as main_module
from app.database.session import get_db
from app.modules.resources.models import Resource, ResourceReservation
from app.modules.appointments.models import Appointment
from app.modules.copilot import query
from app.modules.tickets.models import QueueTicket
from app.modules.tickets.schemas import TicketCreate
from app.modules.tickets.service import create_queue_ticket
from app.modules.institutes.models import Institute
from app.modules.waitlist.originals import fingerprint
from test_postgres_scheduling_4d import postgres_flow
from test_ticket_workflow import _bootstrap_reference_data, _auth_headers

FIRST = datetime(2026, 10, 10, 10, tzinfo=timezone.utc)


def exercise(client, engine, institute, employee, service):
    with Session(engine) as db:
        ticket = create_queue_ticket(db, TicketCreate(institute_id=institute, service_id=service))
        db.add(Institute(id="rr_foreign", region_id=db.get(Institute, institute).region_id, name="Private", city="Other"))
        db.flush()
        db.add(Resource(id="foreign_resource", institute_id="rr_foreign", name="Private foreign", kind="room", capabilities=[], status="active"))
        db.add(Resource(id="selected_resource", institute_id=institute, name="Private room", kind="room", capabilities=[], status="active"))
        db.add(QueueTicket(id="foreign_owner", institute_id="rr_foreign", ticket_number="Foreign", status="waiting", arrival_time=FIRST))
        db.add(Appointment(id="owned_appointment", institute_id=institute, employee_id=employee, service_id=service,
            customer_name="Private appointment", status="confirmed", start_time=FIRST+timedelta(hours=3), end_time=FIRST+timedelta(hours=4)))
        db.flush()
        db.add(ResourceReservation(id="appointment_reservation", institute_id=institute, resource_id="selected_resource",
            appointment_id="owned_appointment", status="reserved", start_time=FIRST+timedelta(hours=3), end_time=FIRST+timedelta(hours=4)))
        for identity, begin, finish, status, owner in [("a", 0, 60, "reserved", ticket.id),
                ("b", 30, 90, "in_use", ticket.id), ("adjacent", 90, 120, "reserved", ticket.id),
                ("released", 0, 120, "released", ticket.id), ("invalid_owner", 0, 120, "reserved", "foreign_owner"),
                ("overdue", -4320, -4260, "reserved", ticket.id)]:
            db.add(ResourceReservation(id=identity, institute_id=institute, resource_id="selected_resource",
                ticket_id=owner, status=status, start_time=FIRST+timedelta(minutes=begin), end_time=FIRST+timedelta(minutes=finish)))
        db.commit()
    def post(ui=None, role="responsable_institut"):
        return client.post("/api/v1/copilot/query", headers=_auth_headers(role, institute),
            json={"message": "Examiner les conflits de planning", "ui_context": ui if ui is not None else {"resource_id": "selected_resource", "day": "2026-10-10"}})
    statements = []
    def collect(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lstrip().split()[0].upper())
    event.listen(engine, "before_cursor_execute", collect)
    try:
        response = post()
        assert response.status_code == 200, response.text
        evidence = response.json()["evidence"]
        result = evidence["result"]
        assert result["resource_id"] == "selected_resource" and result["source_count"] == 4
        assert result["overlap_count"] == 1 and result["overlaps"][0]["duration_us"] == "1800000000"
        assert result["invalid_source_count"] == 1 and result["overdue_unreleased_source_count"] >= 1
        assert not result["booking_authorized"] and not result["complete_institute_conflict_coverage"]
        assert evidence["fingerprint"] == fingerprint({k: v for k, v in evidence.items() if k != "fingerprint"})
        assert "Private" not in response.text and "foreign_owner" not in response.text and "invalid_owner" not in response.text
        assert '"id":"released"' not in response.text
        assert response.json()["actions"] == []
    finally:
        event.remove(engine, "before_cursor_execute", collect)
    assert not set(statements) & {"INSERT", "UPDATE", "DELETE", "ALTER", "CREATE", "DROP"}
    assert post(role="accueil").status_code == 403
    assert post({"resource_id": "foreign_resource", "day": "2026-10-10"}).status_code == 404
    assert post({"resource_id": "selected_resource", "employee_id": employee, "day": "2026-10-10"}).status_code == 400
    assert post({"resource_id": "selected_resource"}).json()["status"] == "clarification"
    assert len(query.REGISTRY["PLANNING_CONFLICTS"].input_schema["oneOf"]) == 2
    assert len(query.REGISTRY["PLANNING_CONFLICTS"].output_schema["anyOf"]) == 2
    with Session(engine) as db:
        db.get(Resource, "selected_resource").status = "maintenance"
        db.commit()
    assert post().json()["evidence"]["result"]["resource_status"] == "maintenance"


def test_sqlite_resource_reservations_scoped(client):
    institute, employees, services = _bootstrap_reference_data(client)
    exercise(client, main_module.engine, institute, employees[0]["id"], services[0]["id"])


def test_postgres_resource_reservations_scoped(client, postgres_flow, monkeypatch):
    engine, institute, employee, service = postgres_flow
    def database():
        with Session(engine) as db:
            yield db
    main_module.app.dependency_overrides[get_db] = database
    monkeypatch.setattr(main_module, "engine", engine)
    exercise(client, engine, institute, employee, service)
